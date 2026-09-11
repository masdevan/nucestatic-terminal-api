nucestatic-terminal-api
├── .env
├── .env.example
├── .gitignore
├── main.py
├── migrate.py
├── readme.md
├── requirements.txt
├── rules.md
├── structure.md
└── app
    ├── api
    │   ├── controllers
    │   │   └── auth.py
    │   ├── models
    │   │   ├── auth.py
    │   │   ├── bookmark.py
    │   │   ├── bridge.py
    │   │   └── user.py
    │   ├── routes
    │   │   ├── auth.py
    │   │   ├── bookmarks.py
    │   │   ├── bridges.py
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
        │   └── version_20260911_bridge_apis.py
        ├── models
        │   ├── bookmark.py
        │   ├── bridge.py
        │   └── user.py
        └── seeders
            ├── bridge_seeder.py
            └── user_seeder.py