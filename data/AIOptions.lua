--
-- Custom Options Definition Table format
--
-- A detailed example of how this format works can be found
-- in the spring source under:
-- AI/Skirmish/NullAI/data/AIOptions.lua
--
--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

local options = {
	{ -- section
		key    = 'performance',
		name   = 'Performance Relevant Settings',
		desc   = 'These settings may be relevant for both CPU usage and AI difficulty.',
		type   = 'section',
	},
	{ -- bool
		key     = 'cheating',
		name    = 'LOS vision',
		desc    = 'Enable global sight',
		type    = 'bool',
		section = 'performance',
		def     = false,
	},
	{ -- bool
		key     = 'comm_merge',
		name    = 'Merge neighbour highBars',
		desc    = 'Merge spatially close highBar ally commanders',
		type    = 'bool',
		section = 'performance',
		def     = false,
	},
	{ -- bool
		key     = 'ally_base',
		name    = 'Avoid building in allied bases',
		desc    = 'Do not build units near allied factories',
		type    = 'bool',
		section = 'performance',
		def     = true,
	},
-- 	{ -- number (int->uint)
-- 		key     = 'random_seed',
-- 		name    = 'Random seed',
-- 		desc    = 'Seed for random number generator (int)',
-- 		type    = 'number',
-- 		def     = 1337
-- 	},

	{ -- string
		key     = 'disabledunits',
		name    = 'Disabled units',
		desc    = 'Disable usage of specific units.\nSyntax: armwar+armpw+raveparty\nkey: disabledunits',
		type    = 'string',
		def     = '',
	},
--	{ -- string
--		key     = 'json',
--		name    = 'JSON',
--		desc    = 'Per-AI config.\nkey: json',
--		type    = 'string',
--		def     = '',
--	},

	{ -- bool
		key     = 'game_config',
		name    = 'Load game config',
		desc    = 'Enable loading of game-side config',
		type    = 'bool',
		def     = true,
	},
	{ -- bool (HighBarV3: gate for built-in decision logic; FR-016, FR-017)
		key     = 'enable_builtin',
		name    = 'Enable built-in AI (disabled)',
		desc    = 'Compatibility option retained for old startscripts. HighBarV3 always disables BARb/Circuit built-in decision modules; external clients are the sole decision authority.',
		type    = 'bool',
		def     = false,
	},
	{ -- list
		key     = 'profile',
		name    = 'Difficulty profile',
		desc    = 'Difficulty or play-style of AI (see init.as).\nkey: profile',
		type    = 'list',
		def     = 'dev',
		items   = {
-- 			{
-- 				key  = 'hard',
-- 				name = 'Hard | Balanced',
-- 				desc = 'Difficulty: Hard |Playstyle: Balanced |Made by Flaka',
-- 			},
-- 			{
-- 				key  = 'medium',
-- 				name = 'Medium | Lazy',
-- 				desc = 'Difficulty: Medium |Playstyle: Learning mechanics',
-- 			},
-- 			{
-- 				key  = 'easy',
-- 				name = 'Easy | Slow',
-- 				desc = 'Difficulty: Easy |Playstyle: First launch',
-- 			},
			{
				key  = 'dev',
				name = 'Testing AI',
				desc = 'Testing config',
			},
			{
				key  = 'macro',
				name = 'Macro Tech AI',
				desc = 'Passive macro profile that prioritizes economy, tech, and a varied defensive army.',
			},
		},
	},
}

return options
