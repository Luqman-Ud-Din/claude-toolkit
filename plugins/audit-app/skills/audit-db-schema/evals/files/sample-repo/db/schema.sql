-- Hand-maintained DDL for tables that live outside EF migrations.

-- Negative case: correct table. PK, bounded strings, decimal money, indexed, audit columns.
CREATE TABLE Customers (
    Id INT IDENTITY(1,1) NOT NULL,
    CompanyId INT NOT NULL,
    Code NVARCHAR(32) NOT NULL,
    Name NVARCHAR(200) NOT NULL,
    CreditLimit DECIMAL(18,2) NOT NULL DEFAULT 0,
    CreatedAt DATETIMEOFFSET NOT NULL,
    CreatedBy INT NOT NULL,
    UpdatedAt DATETIMEOFFSET NULL,
    UpdatedBy INT NULL,
    IsDeleted BIT NOT NULL DEFAULT 0,
    RowVersion ROWVERSION,
    CONSTRAINT PK_Customers PRIMARY KEY CLUSTERED (Id)
);
CREATE UNIQUE INDEX IX_Customers_CompanyId_Code ON Customers (CompanyId, Code) WHERE IsDeleted = 0;

-- Planted issue: money as FLOAT; FK OrderId has no index (CustomerId does).
CREATE TABLE Payments (
    Id INT IDENTITY(1,1) NOT NULL,
    CompanyId INT NOT NULL,
    OrderId INT NOT NULL,
    CustomerId INT NOT NULL,
    Amount FLOAT NOT NULL,
    PaidAt DATETIME NOT NULL,
    Reference NVARCHAR(MAX) NULL,
    CreatedAt DATETIMEOFFSET NOT NULL,
    CONSTRAINT PK_Payments PRIMARY KEY (Id),
    CONSTRAINT FK_Payments_Orders FOREIGN KEY (OrderId) REFERENCES Orders (Id) ON DELETE CASCADE,
    CONSTRAINT FK_Payments_Customers FOREIGN KEY (CustomerId) REFERENCES Customers (Id)
);
CREATE INDEX IX_Payments_CustomerId ON Payments (CustomerId);

-- Planted issue: table without a primary key (heap), no audit columns.
CREATE TABLE AuditLogs (
    UserId INT NULL,
    Action NVARCHAR(50) NOT NULL,
    Payload NVARCHAR(MAX) NULL,
    LoggedAt DATETIME NOT NULL
);
