// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — AuthToken impl (T021).

#include "grpc/AuthToken.h"

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <stdexcept>
#include <string>
#include <sys/random.h>   // getrandom(2)
#include <sys/stat.h>
#include <unistd.h>

namespace circuit::grpc {

namespace {

constexpr std::size_t kTokenBits = 256;
constexpr std::size_t kTokenBytes = kTokenBits / 8;

std::string HexEncode(const unsigned char* bytes, std::size_t n) {
	static constexpr char kHex[] = "0123456789abcdef";
	std::string out;
	out.resize(n * 2);
	for (std::size_t i = 0; i < n; ++i) {
		out[i * 2]     = kHex[bytes[i] >> 4];
		out[i * 2 + 1] = kHex[bytes[i] & 0x0f];
	}
	return out;
}

}  // namespace

AuthToken AuthToken::Generate(const std::string& path) {
	unsigned char raw[kTokenBytes];
	std::size_t filled = 0;
	while (filled < kTokenBytes) {
		const ssize_t n = ::getrandom(raw + filled, kTokenBytes - filled, 0);
		if (n < 0) {
			if (errno == EINTR) continue;
			throw std::runtime_error(std::string("getrandom failed: ") + std::strerror(errno));
		}
		filled += static_cast<std::size_t>(n);
	}

	AuthToken t;
	t.value_ = HexEncode(raw, kTokenBytes);
	t.file_path_ = path;

	// Write atomically: create a `.tmp` sibling, write + fsync, rename.
	// This avoids a window where the file exists but is empty.
	const std::string tmp_path = path + ".tmp";
	const int fd = ::open(tmp_path.c_str(),
	                      O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC,
	                      S_IRUSR | S_IWUSR);  // 0600
	if (fd < 0) {
		throw std::runtime_error("open " + tmp_path + ": " + std::strerror(errno));
	}

	const std::string line = t.value_ + "\n";
	ssize_t written = 0;
	while (static_cast<std::size_t>(written) < line.size()) {
		const ssize_t n = ::write(fd, line.data() + written, line.size() - written);
		if (n < 0) {
			if (errno == EINTR) continue;
			::close(fd);
			::unlink(tmp_path.c_str());
			throw std::runtime_error("write " + tmp_path + ": " + std::strerror(errno));
		}
		written += n;
	}
	if (::fsync(fd) < 0) {
		const int saved = errno;
		::close(fd);
		::unlink(tmp_path.c_str());
		throw std::runtime_error("fsync " + tmp_path + ": " + std::strerror(saved));
	}
	::close(fd);

	if (::rename(tmp_path.c_str(), path.c_str()) < 0) {
		const int saved = errno;
		::unlink(tmp_path.c_str());
		throw std::runtime_error("rename " + tmp_path + " → " + path + ": "
		                         + std::strerror(saved));
	}
	return t;
}

void AuthToken::Unlink() const {
	if (file_path_.empty()) return;
	if (::unlink(file_path_.c_str()) < 0 && errno != ENOENT) {
		// Best-effort; a surviving token file will be overwritten by
		// the next plugin run.
	}
}

bool AuthToken::ConstantTimeEquals(const std::string& a, const std::string& b) {
	if (a.size() != b.size()) {
		// Length difference still leaks through the outer compare;
		// we intentionally return early because gRPC metadata values
		// are pre-fixed length in our contract (64 hex chars).
		return false;
	}
	unsigned char diff = 0;
	for (std::size_t i = 0; i < a.size(); ++i) {
		diff |= static_cast<unsigned char>(a[i]) ^ static_cast<unsigned char>(b[i]);
	}
	return diff == 0;
}

}  // namespace circuit::grpc
