nucestatic-terminal-api/
├── app
│   ├── api
│   │   ├── controllers
│   │   │   └── auth.py
│   │   ├── models
│   │   │   ├── ai_rule.py
│   │   │   ├── ai_session.py
│   │   │   ├── alarm.py
│   │   │   ├── auth.py
│   │   │   ├── backtest.py
│   │   │   ├── bookmark.py
│   │   │   ├── bridge.py
│   │   │   ├── broker.py
│   │   │   ├── cron.py
│   │   │   ├── indicator.py
│   │   │   ├── opencode_settings.py
│   │   │   └── user.py
│   │   ├── routes
│   │   │   ├── ai_rules.py
│   │   │   ├── ai_sessions.py
│   │   │   ├── alarms.py
│   │   │   ├── auth.py
│   │   │   ├── backtest_candles.py
│   │   │   ├── backtest_history.py
│   │   │   ├── backtest_sessions.py
│   │   │   ├── backtest_shared.py
│   │   │   ├── backtest_trade_state.py
│   │   │   ├── bookmarks.py
│   │   │   ├── bridges.py
│   │   │   ├── broker_accounts.py
│   │   │   ├── broker_orders.py
│   │   │   ├── broker_shared.py
│   │   │   ├── brokers.py
│   │   │   ├── cron_jobs.py
│   │   │   ├── indicator_settings.py
│   │   │   ├── indicators.py
│   │   │   ├── opencode_chat.py
│   │   │   ├── opencode_models.py
│   │   │   ├── opencode_settings.py
│   │   │   ├── opencode_test.py
│   │   │   ├── stats.py
│   │   │   └── users.py
│   │   └── utils
│   │       ├── security.py
│   │       ├── urls.py
│   │       └── values.py
│   └── databases
│       ├── migrations
│       │   ├── manager.py
│       │   ├── version_20260910_users.py
│       │   ├── version_20260911_bookmarks.py
│       │   ├── version_20260911_bridge_apis.py
│       │   ├── version_20260916_scripts.py
│       │   ├── version_20260917_indicators.py
│       │   ├── version_20260918_indicator_names.py
│       │   ├── version_20260919_alarms.py
│       │   ├── version_20260920_brokers.py
│       │   ├── version_20260921_broker_accounts.py
│       │   ├── version_20260922_broker_orders.py
│       │   ├── version_20260923_backtest.py
│       │   ├── version_20260923_opencode_settings.py
│       │   ├── version_20260924_backtest_trades.py
│       │   ├── version_20260924_opencode_settings_multi.py
│       │   ├── version_20260925_backtest_history.py
│       │   ├── version_20260926_backtest_history_session.py
│       │   ├── version_20260927_backtest_history_names.py
│       │   ├── version_20260928_backtest_alarms.py
│       │   ├── version_20260929_backtest_metrics.py
│       │   ├── version_20260930_backtest_order_tickets.py
│       │   ├── version_20260931_backtest_provider.py
│       │   ├── version_20260932_ai_sessions.py
│       │   ├── version_20260933_ai_rules.py
│       │   ├── version_20260934_ai_sessions_reverted.py
│       │   ├── version_20260935_ai_sessions_usage.py
│       │   ├── version_20260936_bookmarks_bridge.py
│       │   ├── version_20260937_bookmarks_bridge_unique.py
│       │   ├── version_20260938_indicator_settings.py
│       │   ├── version_20260939_builtin_indicator_names.py
│       │   ├── version_20260940_backtest_session_metrics.py
│       │   └── version_20260941_cron_jobs.py
│       ├── models
│       │   ├── alarm.py
│       │   ├── bookmark.py
│       │   ├── bridge.py
│       │   └── user.py
│       ├── seeders
│       │   ├── bridge_seeder.py
│       │   └── user_seeder.py
│       ├── base.py
│       └── config.py
├── .dockerignore
├── .env
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── main.py
├── migrate.py
├── readme.md
├── requirements.txt
├── rules.md
├── structure.md
├── update.sh
└── worker/
    ├── Dockerfile
    ├── alarms.js
    ├── bridge.js
    ├── index.js
    ├── indicator.js
    └── package.json
