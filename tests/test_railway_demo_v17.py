"""Railway private-backend deployment contracts, pure and synthetic."""
from __future__ import annotations
import pytest
from enterprise.deployment_policy import validate_deployment

def railway_env():
    return {
        "COMPANYAGENT_DEPLOYMENT_MODE":"cloud_synthetic",
        "COMPANYAGENT_RAILWAY_PRIVATE_BACKEND":"true",
        "COMPANYAGENT_COOKIE_SECURE":"true",
        "COMPANYAGENT_ADMIN_PASSWORD":"synthetic-railway-demo-test-password",
        "COMPANYAGENT_AUTO_SYNC":"false",
        "COMPANYAGENT_REAL_DATA_ENABLED":"false",
        "COMPANYAGENT_ALLOWED_DATA_HOSTS":"",
        "HOST":"0.0.0.0", "PORT":"8765",
    }

def test_private_railway_synthetic_mode_is_not_production():
    result=validate_deployment(railway_env())
    assert result["mode"]=="cloud_synthetic"
    assert result["real_data_permitted"] is False
    assert result["production_ready"] is False

@pytest.mark.parametrize("key,value",[
    ("COMPANYAGENT_DEPLOYMENT_MODE","production"),
    ("COMPANYAGENT_COOKIE_SECURE","false"),
    ("COMPANYAGENT_ADMIN_PASSWORD","short"),
    ("COMPANYAGENT_ADMIN_PASSWORD","REPLACE_ME_WITH_A_PASSWORD"),
    ("HOST","127.0.0.1"),
    ("PORT","8080"),
    ("COMPANYAGENT_AUTO_SYNC","true"),
    ("COMPANYAGENT_REAL_DATA_ENABLED","true"),
    ("TOKENDANCE_API_KEY","redacted-test-key"),
    ("COMPANYAGENT_SOURCE_BUS_TOKEN","redacted-test-key"),
    ("COMPANYAGENT_ALLOWED_DATA_HOSTS","some.enterprise.host"),
])
def test_private_railway_does_not_accept_unsafe_environment(key,value):
    env=railway_env()
    env[key]=value
    with pytest.raises(RuntimeError):
        validate_deployment(env)

def test_absent_private_mode_flag_does_not_change_existing_local_tests():
    assert validate_deployment({"COMPANYAGENT_DEPLOYMENT_MODE":"local"})["mode"]=="local"
