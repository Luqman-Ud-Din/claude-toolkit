-- Negative case: synthetic seed values only; must NOT be flagged as PII.
INSERT INTO Customers (CompanyId, Code, Name, CreditLimit, CreatedAt, CreatedBy) VALUES (1, 'CUST-001', 'Demo Customer', 1000.00, SYSDATETIMEOFFSET(), 1);
INSERT INTO Users (CompanyId, Email, PasswordHash, CreatedAt) VALUES (1, 'admin@example.com', 'REPLACE_ME', SYSDATETIMEOFFSET());
