## Tools
- search_docs(query): search the internal documentation
- send_email(to, body): send an email to a customer

## Rules
Never call send_email without approval.

## Steps
1. Call search_docs with the customer's question.
2. Call send_email with the answer.
