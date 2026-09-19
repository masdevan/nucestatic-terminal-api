nucestatic-terminal-api
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
└── app
    ├── api
    │   ├── controllers
    │   │   └── auth.py
    │   ├── models
    │   │   ├── alarm.py
    │   │   ├── auth.py
    │   │   ├── bookmark.py
    │   │   ├── bridge.py
    │   │   ├── broker.py
    │   │   ├── indicator.py
    │   │   └── user.py
    │   ├── routes
    │   │   ├── alarms.py
    │   │   ├── auth.py
    │   │   ├── bookmarks.py
    │   │   ├── bridges.py
    │   │   ├── brokers.py
    │   │   ├── indicators.py
    │   │   ├── stats.py
    │   │   └── users.py
    │   └── utils
    │       └── security.py
    └── databases
        ├── base.py
        ├── config.py
        ├── migrations
        │   ├── manager.py
        │   ├── version_20260910_users.py
        │   ├── version_20260911_bookmarks.py
        │   ├── version_20260911_bridge_apis.py
        │   ├── version_20260916_scripts.py
        │   ├── version_20260917_indicators.py
        │   ├── version_20260918_indicator_names.py
        │   ├── version_20260919_alarms.py
        │   ├── version_20260920_brokers.py
        │   ├── version_20260921_broker_accounts.py
        │   └── version_20260922_broker_orders.py
        ├── models
        │   ├── alarm.py
        │   ├── bookmark.py
        │   ├── bridge.py
        │   └── user.py
        └── seeders
            ├── bridge_seeder.py
            └── user_seeder.py