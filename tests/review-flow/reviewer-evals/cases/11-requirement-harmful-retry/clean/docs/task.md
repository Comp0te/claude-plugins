# Card checkout

- A customer pays for an order with a card; the order is marked paid once the charge succeeds.
- On a failed card charge, retry the charge up to 3 times with the same idempotency key before reporting the gateway's message to the customer.
