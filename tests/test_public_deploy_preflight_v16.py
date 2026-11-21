"""Rendered public-demo Compose preflight fails closed without logging credentials."""
from __future__ import annotations
import copy
from scripts.public_demo_config_preflight import validate

DUMMY_BCRYPT="$2a$14$Zkx19XLiW6VYouLHR5NmfOFU0z2GTNmpkT/5qqR7hx4IjWJPDhjvG"

def fake_compose():
    return {
        "services":{
            "companyagent":{
                "environment":{
                    "COMPANYAGENT_DEPLOYMENT_MODE":"cloud_synthetic",
                    "COMPANYAGENT_AUTO_SYNC":"false",
                    "COMPANYAGENT_REAL_DATA_ENABLED":"false",
                    "COMPANYAGENT_ALLOWED_DATA_HOSTS":"",
                    "COMPANYAGENT_ADMIN_PASSWORD":"synthetic-but-unique-app-password-ci"},
                "read_only":True,
                "cap_drop":["ALL"],
                "networks":{"backend":None},
                "tmpfs":["/app/runtime:rw","/tmp:rw"],
            },
            "caddy":{
                "environment":{"PUBLIC_DEMO_DOMAIN":"pilot.company-example.org",
                               "PUBLIC_DEMO_USER":"reviewer",
                               "PUBLIC_DEMO_BCRYPT_HASH":DUMMY_BCRYPT},
                "networks":{"edge":None,"backend":None},
                "ports":[{"target":80,"published":"80","protocol":"tcp"},{"target":443,"published":"443","protocol":"tcp"}],
            },
        },
        "networks":{"edge":{},"backend":{"internal":True}}
    }


def test_valid_secure_public_compose_accepts_preflight():
    assert validate(fake_compose())==[]


def test_bcrypt_with_doubled_dollars_is_accepted_as_docker_rendering():
    x=fake_compose()
    x["services"]["caddy"]["environment"]["PUBLIC_DEMO_BCRYPT_HASH"]=DUMMY_BCRYPT.replace("$","$$")
    assert validate(x)==[]


def test_public_host_rejects_placeholder_and_plain_text_password():
    x=fake_compose()
    x["services"]["caddy"]["environment"].update({"PUBLIC_DEMO_DOMAIN":"demo.example.com",
                                                     "PUBLIC_DEMO_BCRYPT_HASH":"plaintext-password"})
    errors=validate(x)
    assert any("hostname" in e or "suffix" in e for e in errors)
    assert any("bcrypt" in e for e in errors)


def test_backend_published_port_is_rejected():
    x=fake_compose();x["services"]["companyagent"]["ports"]=[{"target":8765,"published":"8765"}]
    assert any("MUST NOT publish" in e for e in validate(x))


def test_bridge_network_is_required_and_internal():
    x=fake_compose();x["networks"]["backend"]["internal"]=False
    assert any("internal" in e for e in validate(x))


def test_enterprise_secrets_forbidden_even_for_authenticated_public_demo():
    x=fake_compose();x["services"]["companyagent"]["environment"]["TOKENDANCE_API_KEY"]="synthetic-token-value"
    assert any("credentials" in e for e in validate(x))


def test_demo_never_claims_production_mode():
    x=fake_compose();x["services"]["companyagent"]["environment"]["COMPANYAGENT_DEPLOYMENT_MODE"]="production"
    assert any("cloud_synthetic" in e for e in validate(x))
