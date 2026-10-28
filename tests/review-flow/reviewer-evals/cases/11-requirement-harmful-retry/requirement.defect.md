# Card checkout

- A customer pays for an order with a card; the order is marked paid once the charge succeeds.
- On a failed card charge, retry the charge up to 3 times before reporting the gateway's message to the customer.
- Only a transient failure is retried: a timeout or a 5xx answer. A decline (4xx) is reported at once, without a retry.
- "Up to 3 times" counts total attempts, the first one included.
