from mangum import Mangum
from app.main import app

# API Gateway v2 -> FastAPI. Database schema is migrated before deployment, not at cold start.
handler = Mangum(app, lifespan="off")
