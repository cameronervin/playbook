# Code Smell Patterns (AI Slop Detection)

Common patterns that indicate AI-generated code that needs cleanup.

## Overly Verbose Code

### Pattern: One-liner spread across many lines
```python
# Bad: AI slop
def get_user_name(user):
    if user is not None:
        if user.name is not None:
            name = user.name
            return name
        else:
            return None
    else:
        return None

# Good: Simplified
def get_user_name(user):
    return user.name if user else None
```

### Pattern: Excessive obvious comments
```python
# Bad: Comments stating the obvious
def add(a, b):
    # Add a and b together
    result = a + b  # Store the result of adding a and b
    # Return the result
    return result  # Return the sum

# Good: Self-documenting code
def add(a: int, b: int) -> int:
    return a + b
```

### Pattern: Redundant null checks
```typescript
// Bad: Redundant checks
if (user !== null && user !== undefined) {
    if (user.name !== null && user.name !== undefined) {
        return user.name;
    }
}

// Good: Optional chaining
return user?.name;
```

## Inconsistent Patterns

### Pattern: Same operation done different ways
```python
# File 1: Using async/await
async def get_user(id: int):
    async with session.begin():
        return await session.get(User, id)

# File 2: Using sync style (inconsistent!)
def get_user(id: int):
    with session.begin():
        return session.query(User).filter_by(id=id).first()

# Fix: Pick one pattern and use it everywhere
```

### Pattern: Mixed error handling
```python
# File 1: Raises exceptions
def process_a():
    if error:
        raise ValueError("Failed")

# File 2: Returns error codes (inconsistent!)
def process_b():
    if error:
        return {"error": "Failed"}

# Fix: Consistent exception handling
```

## Hand-Rolled Utilities

### Pattern: Custom implementations of common operations
```python
# Bad: Hand-rolled retry
def fetch_with_retry(url, max_retries=3):
    for i in range(max_retries):
        try:
            return requests.get(url)
        except Exception:
            if i == max_retries - 1:
                raise
            time.sleep(2 ** i)

# Good: Use tenacity
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential())
def fetch(url):
    return requests.get(url)
```

### Pattern: Manual date formatting
```python
# Bad: Hand-rolled date formatting
def format_date(dt):
    return f"{dt.year}-{str(dt.month).zfill(2)}-{str(dt.day).zfill(2)}"

# Good: Use strftime
def format_date(dt):
    return dt.strftime("%Y-%m-%d")
```

## Magic Strings

### Pattern: Hardcoded status strings
```python
# Bad: Magic strings everywhere
if order.status == "pending":
    order.status = "processing"
elif order.status == "processing":
    order.status = "completed"

# Good: Use enum/constants
class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"

if order.status == OrderStatus.PENDING:
    order.status = OrderStatus.PROCESSING
```

### Pattern: Hardcoded error messages
```python
# Bad: Duplicated error strings
raise HTTPException(status_code=404, detail="User not found")
# ... in another file ...
raise HTTPException(status_code=404, detail="User not found")

# Good: Centralized error messages
class ErrorMessages:
    USER_NOT_FOUND = "User not found"
    
raise HTTPException(status_code=404, detail=ErrorMessages.USER_NOT_FOUND)
```

## Duplicate Logic

### Pattern: Copy-paste with minor variations
```python
# File 1
def create_user(data):
    user = User(**data)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

# File 2 (copy-paste!)
def create_order(data):
    order = Order(**data)
    session.add(order)
    session.commit()
    session.refresh(order)
    return order

# Good: Generic repository pattern
class BaseRepository:
    def create(self, model_class, data):
        instance = model_class(**data)
        self.session.add(instance)
        self.session.commit()
        self.session.refresh(instance)
        return instance
```

## Boundary Violations

### Pattern: Skipping layers
```python
# Bad: Route directly accessing repository
@router.get("/users/{id}")
async def get_user(id: int, repo: UserRepository = Depends()):
    return repo.get_by_id(id)  # Skipping service layer!

# Good: Route calls service, service calls repository
@router.get("/users/{id}")
async def get_user(id: int, service: UserService = Depends()):
    return service.get_user(id)
```

### Pattern: Business logic in routes
```python
# Bad: Business logic in route
@router.post("/orders")
async def create_order(data: OrderCreate):
    # Validation
    if data.quantity > 100:
        raise HTTPException(400, "Max 100 items")
    # Discount calculation
    discount = 0.1 if data.quantity > 10 else 0
    # Tax calculation
    tax = data.price * 0.08
    # This should all be in a service!

# Good: Thin route, fat service
@router.post("/orders")
async def create_order(data: OrderCreate, service: OrderService = Depends()):
    return service.create_order(data)
```

## Detection Commands

```bash
# Find files with many lines (potential god classes)
find . -name "*.py" -exec wc -l {} + | sort -rn | head -20

# Find duplicate function names
rg "^def \w+|^async def \w+" -o | sort | uniq -d

# Find magic strings
rg '(status|state|type)\s*==\s*["\'][a-z]+["\']' --type py

# Find TODO/FIXME comments (deferred cleanup)
rg "TODO|FIXME|HACK|XXX" --type py --type ts

# Find commented-out code (Python)
rg "^\s*#\s*(def|class|if|for|while|return)" --type py

# Find large functions (may need splitting)
# Use AST analysis or code complexity tools
```
