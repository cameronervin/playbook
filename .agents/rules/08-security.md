# Security Rules

## DO
- Validate ALL input with Pydantic
- Use `fastapi-users` for auth
- Hash passwords (bcrypt)
- Use HTTPS in production
- Set CORS origins explicitly
- Use parameterized queries (SQLAlchemy)

## DON'T
- Log passwords or tokens
- Expose stack traces in production
- Trust client-side validation alone
- Store secrets in code or git
- Use `*` for CORS in production

## Secrets
| Environment | Method |
|-------------|--------|
| Local | `.env` file |
| Dev/Test | `.env` with placeholders |
| Production | Secrets Manager |

## Validation
```python
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
```
