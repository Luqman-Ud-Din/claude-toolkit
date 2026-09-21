-- Subscriptions schema (SQL Server)
CREATE TABLE Subscriptions (
    Id INT IDENTITY PRIMARY KEY,
    CustomerId INT NOT NULL,
    -- correct (negative case): offset-aware instant
    CreatedAt datetimeoffset NOT NULL,
    -- ISSUE: instant stored in a zone-less column with a server-local default
    TrialEndsAt datetime2 NOT NULL DEFAULT GETDATE(),
    -- correct (negative case): true date-only concept
    BillingAnchorDate date NOT NULL
);

CREATE TABLE Branches (
    Id INT IDENTITY PRIMARY KEY,
    IanaTimeZone NVARCHAR(64) NOT NULL DEFAULT 'Asia/Karachi'
);
