# TDD Workflow

## When to Apply TDD
Use TDD for **non-trivial features** (3+ steps, new logic, refactoring):
- New service/repository methods
- API endpoints with business logic
- Refactoring existing functionality
- Bug fixes (write failing test first)

Skip TDD for: config changes, simple CRUD, dependency updates, docs.

## The TDD Cycle
```
1. RED    → Write failing test first
2. GREEN  → Write minimal code to pass
3. REFACTOR → Clean up, maintain tests passing
```

## Workflow Steps

### 1. RED: Write Failing Test
```python
# ❌ Start with a test that fails
def test_calculate_discount_applies_bulk_rate():
    service = PricingService()
    result = service.calculate_discount(quantity=100, base_price=10.00)
    assert result == 8.50  # 15% bulk discount
```

Run test → confirm it fails → then write implementation.

### 2. GREEN: Minimal Implementation
```python
# ✅ Just enough to pass
def calculate_discount(self, quantity: int, base_price: float) -> float:
    if quantity >= 100:
        return base_price * 0.85
    return base_price
```

### 3. REFACTOR: Clean Code
- Extract constants, improve naming
- Remove duplication
- **Keep tests passing**

## Before Implementing Features
```
□ Write test describing expected behavior
□ Run test → verify it fails
□ Implement minimal solution
□ Run test → verify it passes
□ Refactor if needed
□ All tests still pass
```

## Test-First Benefits
- Forces clear requirements before coding
- Prevents over-engineering (minimal implementation)
- Creates living documentation
- Catches regressions immediately
