// Compatibility shim: CEnemyInfo is defined in EnemyUnit.h (alongside
// CEnemyUnit). Several V3 translation units were authored against a
// standalone EnemyInfo.h that doesn't exist upstream; this forwards
// the include.
#pragma once
#include "unit/enemy/EnemyUnit.h"
