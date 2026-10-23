import pytest
import app.core as core


@pytest.fixture(autouse=True)
def reset_login_rate_limit():
    # All TestClient requests share one client IP; keep rate-limit state per test.
    core._failed.clear()
    core._failed_ip.clear()
    yield
    core._failed.clear()
    core._failed_ip.clear()
