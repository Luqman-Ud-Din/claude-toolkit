-- Ledger schema (SQL Server)
CREATE TABLE Users (
    Id INT IDENTITY PRIMARY KEY,
    Email NVARCHAR(256) NOT NULL,          -- ISSUE: no UNIQUE index; UsersController relies on an Any() check
    PasswordHash NVARCHAR(512) NOT NULL
);

CREATE TABLE Orders (
    Id INT IDENTITY PRIMARY KEY,
    CustomerId INT NOT NULL,
    Total DECIMAL(18,2) NOT NULL,
    Status INT NOT NULL
);

CREATE TABLE WebhookEvents (
    Id INT IDENTITY PRIMARY KEY,
    Provider NVARCHAR(32) NOT NULL,
    EventId NVARCHAR(128) NOT NULL,
    ReceivedAt DATETIMEOFFSET NOT NULL
);
-- correct (negative case): dedupe is enforced by the database
CREATE UNIQUE INDEX UX_WebhookEvents_Provider_EventId ON WebhookEvents (Provider, EventId);

CREATE TABLE Stock (
    Id INT IDENTITY PRIMARY KEY,
    ProductId INT NOT NULL,
    Quantity INT NOT NULL
);
