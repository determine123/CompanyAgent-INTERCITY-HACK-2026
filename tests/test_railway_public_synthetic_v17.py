"""Public Railway single-container launcher must fail closed before network."""
from __future__ import annotations
import pytest
from deploy.railway.start import validate_public_config

CI_BCRYPT="$2a$14$Zkx19XLiW6VYouLHR5NmfOFU0z2GTNmpkT/5qqR7hx4IjWJPDhjvG"
def good():
    return {
        "COMPANYAGENT_DEPLOYMENT_MODE":"cloud_synthetic",
        "COMPANYAGENT_COOKIE_SECURE":"true",
        "COMPANYAGENT_AUTO_SYNC":"false",
        "COMPANYAGENT_REAL_DATA_ENABLED":"false",
        "COMPANYAGENT_ALLOWED_DATA_HOSTS":"",
        "PORT":"18080",
        "PUBLIC_DEMO_USER":"reviewer",
        "PUBLIC_DEMO_BCRYPT_HASH":CI_BCRYPT,
        "COMPANYAGENT_ADMIN_PASSWORD":"ci-synthetic-second-secret-password",
    }

def test_railway_synthetic_with_two_credentials_validates():
    r=validate_public_config(good())
    assert r=={"mode":"cloud_synthetic","port":18080,"production_ready":False}

@pytest.mark.parametrize("bad",[
    {"COMPANYAGENT_DEPLOYMENT_MODE":"production"},
    {"COMPANYAGENT_DEPLOYMENT_MODE":"local"},
    {"COMPANYAGENT_COOKIE_SECURE":"false"},
    {"PORT":"8765"},
    {"PORT":"80"},
    {"PORT":"abc"},
    {"PUBLIC_DEMO_USER":""},
    {"PUBLIC_DEMO_USER":"a"},
    {"PUBLIC_DEMO_BCRYPT_HASH":"plaintext"},
    {"PUBLIC_DEMO_BCRYPT_HASH":""},
    {"COMPANYAGENT_ADMIN_PASSWORD":"weak"},
    {"TOKENDANCE_API_KEY":"fake-token"},
    {"B1X_API_KEY":"fake-token"},
    {"COMPANYAGENT_ALLOWED_DATA_HOSTS":"internal.company.example"},
    {"COMPANYAGENT_REAL_DATA_ENABLED":"true"},
    {"COMPANYAGENT_AUTO_SYNC":"true"},
    {"COMPANYAGENT_SOURCE_STOCK_TOKEN":"fake-token"},
])
def test_railway_cannot_start_insecure_config(bad):
    x=good()
    x.update(bad)
    with pytest.raises(RuntimeError):
        validate_public_config(x)
