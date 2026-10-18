import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db, Base

# Use SQLite for testing
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_create_task():
    response = client.post("/tasks", json={
        "title": "Test task",
        "description": "A test task",
        "priority": "high"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test task"
    assert data["priority"] == "high"
    assert data["completed"] == False

def test_list_tasks():
    client.post("/tasks", json={"title": "Task 1"})
    client.post("/tasks", json={"title": "Task 2"})
    response = client.get("/tasks")
    assert response.status_code == 200
    assert len(response.json()) == 2

def test_get_task():
    create_resp = client.post("/tasks", json={"title": "Find me"})
    task_id = create_resp.json()["id"]
    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Find me"

def test_update_task():
    create_resp = client.post("/tasks", json={"title": "Old title"})
    task_id = create_resp.json()["id"]
    response = client.put(f"/tasks/{task_id}", json={"title": "New title", "completed": True})
    assert response.status_code == 200
    assert response.json()["title"] == "New title"
    assert response.json()["completed"] == True

def test_delete_task():
    create_resp = client.post("/tasks", json={"title": "Delete me"})
    task_id = create_resp.json()["id"]
    response = client.delete(f"/tasks/{task_id}")
    assert response.status_code == 200
    get_resp = client.get(f"/tasks/{task_id}")
    assert get_resp.status_code == 404

def test_task_not_found():
    response = client.get("/tasks/99999")
    assert response.status_code == 404

def test_invalid_priority():
    response = client.post("/tasks", json={"title": "Bad priority", "priority": "urgent"})
    assert response.status_code == 422
