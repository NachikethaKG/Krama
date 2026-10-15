"""Unit tests for regex secret masking and structured data sanitization."""

from app.policy.masking import (
    is_sensitive_key,
    mask_dict,
    mask_prompt,
    mask_text,
)


def test_mask_private_keys() -> None:
    tag_start = "BEG" + "IN"
    tag_key = "PRIVATE " + "KEY"
    header = f"-----{tag_start} RSA {tag_key}-----"
    footer = f"-----END RSA {tag_key}-----"
    rsa_key = f"{header}\nMIIEowIBAAKCAQEA0Y8v...test_private_key_data...\n{footer}"
    result = mask_text(rsa_key)
    assert "test_private_key_data" not in result
    assert "[REDACTED]" in result

    ssh_header = f"-----{tag_start} OPENSSH {tag_key}-----"
    ssh_footer = f"-----END OPENSSH {tag_key}-----"
    openssh_key = f"{ssh_header}\nb3BlbnNzaC1rZXktdjEAAAA...\n{ssh_footer}"
    assert mask_text(openssh_key) == "[REDACTED]"


def test_mask_bearer_tokens_and_jwts() -> None:
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisSignature"
    header = f"Authorization: Bearer {jwt}"
    masked = mask_text(header)
    assert "doNotLeakThisSignature" not in masked
    assert "Bearer [REDACTED]" in masked

    raw_jwt_text = f"Received token {jwt} in response"
    assert "doNotLeakThisSignature" not in mask_text(raw_jwt_text)
    assert "[REDACTED]" in mask_text(raw_jwt_text)

    generic_bearer = "Authorization: Bearer 1234567890abcdef123456"
    assert "1234567890abcdef123456" not in mask_text(generic_bearer)
    assert "Bearer [REDACTED]" in mask_text(generic_bearer)


def test_mask_vendor_api_keys() -> None:
    github_pat = "ghp_123456789012345678901234567890123456"
    assert mask_text(f"Token: {github_pat}") == "Token: [REDACTED]"

    gitea_token = "gitea_abcdef1234567890abcdef"
    assert mask_text(f"Key: {gitea_token}") == "Key: [REDACTED]"

    openai_key = "sk-1234567890abcdefghijklmnopqrstuv"
    assert mask_text(f"OpenAI: {openai_key}") == "OpenAI: [REDACTED]"

    aws_key = "AKIAIOSFODNN7EXAMPLE"
    assert mask_text(f"AWS: {aws_key}") == "AWS: [REDACTED]"

    slack_token = "xoxb-1234567890-abcdefghij"
    assert mask_text(f"Slack: {slack_token}") == "Slack: [REDACTED]"


def test_mask_key_value_secrets() -> None:
    cases = [
        ('password="SuperSecretP@ssword123!"', 'password="[REDACTED]"'),
        ('"password": "SuperSecretP@ssword123!"', '"password": "[REDACTED]"'),
        ("api_key: 'sk_secret_value_12345'", "api_key: '[REDACTED]'"),
        ("auth_token=my_secret_token_val", "auth_token=[REDACTED]"),
        ('client_secret: "super_secret_payload"', 'client_secret: "[REDACTED]"'),
        ("passwd=SecretPass999", "passwd=[REDACTED]"),
    ]
    for raw, expected in cases:
        assert mask_text(raw) == expected


def test_mask_action_instructions() -> None:
    action1 = "fill 'input[name=\"password\"]' 'SuperSecretP@ssword123!'"
    assert mask_text(action1) == "fill 'input[name=\"password\"]' '[REDACTED]'"

    action2 = 'type "input#token" "SecretToken12345"'
    assert mask_text(action2) == 'type "input#token" "[REDACTED]"'


def test_mask_aria_snapshots() -> None:
    aria = '- textbox "Password": SuperSecretP@ssword123!'
    assert mask_text(aria) == '- textbox "Password": [REDACTED]'

    aria_secret = '- textbox "API Secret": SecretKey12345'
    assert mask_text(aria_secret) == '- textbox "API Secret": [REDACTED]'


def test_mask_url_credentials() -> None:
    url_with_param = "https://gitea.local/api/v1/repos?token=gitea_secret_token_123456"
    assert "gitea_secret_token_123456" not in mask_text(url_with_param)
    assert "token=[REDACTED]" in mask_text(url_with_param)

    basic_auth_url = "https://krama_user:SecretP@ssword@gitea.local/repo.git"
    masked_url = mask_text(basic_auth_url)
    assert "SecretP@ssword" not in masked_url
    assert masked_url == "https://krama_user:[REDACTED]@gitea.local/repo.git"


def test_mask_benign_content_preservation() -> None:
    benign_texts = [
        "Click button 'Create repository'",
        "Navigate to /user/settings",
        "Repository name: krama-tutorial-project",
        "Issue #12: Fix typo in documentation",
    ]
    for text in benign_texts:
        assert mask_text(text) == text


def test_mask_with_extra_secrets() -> None:
    text = "The user typed SuperCustomPlaintextPassword into an untyped input"
    masked = mask_text(text, extra_secrets={"SuperCustomPlaintextPassword"})
    assert "SuperCustomPlaintextPassword" not in masked
    assert "[REDACTED]" in masked


def test_is_sensitive_key() -> None:
    assert is_sensitive_key("password")
    assert is_sensitive_key("current_password")
    assert is_sensitive_key("api-key")
    assert is_sensitive_key("auth_token")
    assert is_sensitive_key("Authorization")
    assert not is_sensitive_key("username")
    assert not is_sensitive_key("repo_name")
    assert not is_sensitive_key("description")


def test_mask_dict_structured_data() -> None:
    payload = {
        "username": "admin",
        "password": "SuperSecretP@ssword123!",
        "config": {
            "api_key": "raw_api_key_12345",
            "active": True,
            "port": 8080,
        },
        "log_messages": [
            "User authenticated with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.secretSig",
            "Benign operation completed",
        ],
    }
    sanitized = mask_dict(payload)
    assert sanitized["username"] == "admin"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["config"]["api_key"] == "[REDACTED]"
    assert sanitized["config"]["active"] is True
    assert sanitized["config"]["port"] == 8080
    assert "secretSig" not in sanitized["log_messages"][0]
    assert "[REDACTED]" in sanitized["log_messages"][0]
    assert sanitized["log_messages"][1] == "Benign operation completed"


def test_mask_prompt() -> None:
    # Text prompt
    prompt_str = "Execute action: fill 'input#password' 'SuperSecretP@ssword123!'"
    assert "SuperSecretP@ssword123!" not in mask_prompt(prompt_str)
    assert "[REDACTED]" in mask_prompt(prompt_str)

    # Structured prompt
    prompt_dict = {
        "system": "You are a safe web agent.",
        "user_message": "Fill form with password=SuperSecretP@ssword123!",
    }
    cleaned = mask_prompt(prompt_dict)
    assert isinstance(cleaned, dict)
    assert "SuperSecretP@ssword123!" not in cleaned["user_message"]
    assert "[REDACTED]" in cleaned["user_message"]
