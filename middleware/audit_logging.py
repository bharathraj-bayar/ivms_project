import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from models.database import get_conn
import psycopg2.extras

class AuditLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        resp = await call_next(request)
        duration = int((time.time() - start) * 1000)

        try:
            conn = get_conn(); cur = conn.cursor()
            try:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id SERIAL PRIMARY KEY,
                        path TEXT,
                        method TEXT,
                        status_code INTEGER,
                        duration_ms INTEGER,
                        ip TEXT,
                        user_email TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
                    )
                """)
                conn.commit()
            except Exception:
                pass

            try:
                ip = request.client.host if request.client else None
                user = None
                if 'authorization' in request.headers:
                    # best-effort extract
                    user = request.headers.get('authorization')[:128]
                cur.execute("INSERT INTO audit_log (path, method, status_code, duration_ms, ip, user_email) VALUES (%s,%s,%s,%s,%s,%s)",
                            (str(request.url.path), request.method, resp.status_code, duration, ip, user))
                conn.commit()
            except Exception:
                pass
        except Exception:
            pass
        finally:
            try:
                cur.close(); conn.close()
            except Exception:
                pass

        return resp
