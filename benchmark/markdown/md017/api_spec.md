# Checkout Service API Specification

### GET /v1/cart

Retrieves the current shopping cart for a session.

### POST /v1/cart/items

Adds an item to the shopping cart.

### DELETE /v1/cart/items/{id}

Removes an item from the shopping cart.

### POST /v1/checkout/legacy

Initiates checkout using the legacy single-step flow.

### POST /v2/checkout/session

Initiates checkout using the multi-step session-based flow.
