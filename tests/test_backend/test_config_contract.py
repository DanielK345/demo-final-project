def test_production_readiness_cannot_bypass_missing_durable_service_persistence():
    from src.backend.config import Settings

    settings = Settings(
        app_env="production",
        database_url="postgresql://runtime.example/db",
        database_url_migrations="postgresql://migration.example/db",
        cors_origins="https://app.example.com",
    )
    errors = settings.production_readiness_errors()
    assert "DURABLE_SERVICE_PERSISTENCE_REQUIRED" in errors
    assert all("postgresql://" not in error for error in errors)
