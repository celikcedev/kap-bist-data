-- CreateEnum
CREATE TYPE "StatementType" AS ENUM ('BALANCE_SHEET_ASSETS', 'BALANCE_SHEET_LIABILITIES', 'INCOME_STATEMENT', 'CASH_FLOW');

-- CreateTable
CREATE TABLE "indices" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "details" TEXT,
    "metadata" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "indices_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "main_sectors" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "main_sectors_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sub_sectors" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "mainSectorId" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "sub_sectors_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "markets" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "markets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "companies" (
    "id" SERIAL NOT NULL,
    "code" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "detailUrl" TEXT,
    "mainSectorId" INTEGER,
    "subSectorId" INTEGER,
    "headquartersAddress" TEXT,
    "communicationAddress" TEXT,
    "communicationPhone" TEXT,
    "communicationFax" TEXT,
    "productionFacilities" TEXT[],
    "email" TEXT,
    "website" TEXT,
    "businessScope" TEXT,
    "companyDuration" TEXT,
    "auditor" TEXT,
    "registryOffice" TEXT,
    "registrationDate" TIMESTAMP(3),
    "registrationNumber" TEXT,
    "taxNumber" TEXT,
    "taxOffice" TEXT,
    "paidInCapital" DECIMAL(20,2),
    "authorizedCapital" DECIMAL(20,2),
    "freeFloatTicker" VARCHAR(16),
    "freeFloatAmountTL" DECIMAL(20,2),
    "freeFloatPercent" DECIMAL(5,2),
    "isTradable" BOOLEAN,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "lastScrapedAt" TIMESTAMP(3),

    CONSTRAINT "companies_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "company_indices" (
    "companyId" INTEGER NOT NULL,
    "indexId" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "company_indices_pkey" PRIMARY KEY ("companyId","indexId")
);

-- CreateTable
CREATE TABLE "company_markets" (
    "companyId" INTEGER NOT NULL,
    "marketId" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "company_markets_pkey" PRIMARY KEY ("companyId","marketId")
);

-- CreateTable
CREATE TABLE "ir_staff" (
    "id" SERIAL NOT NULL,
    "companyId" INTEGER NOT NULL,
    "fullName" TEXT NOT NULL,
    "title" TEXT,
    "assignmentDate" TIMESTAMP(3),
    "phone" TEXT,
    "email" TEXT,
    "licenses" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ir_staff_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "board_members" (
    "id" SERIAL NOT NULL,
    "companyId" INTEGER NOT NULL,
    "fullName" TEXT NOT NULL,
    "actingForLegalEntity" TEXT,
    "gender" TEXT,
    "title" TEXT,
    "profession" TEXT,
    "firstElectionDate" TIMESTAMP(3),
    "isExecutive" BOOLEAN,
    "rolesLast5Years" TEXT,
    "externalRoles" TEXT,
    "has5yFinExp" BOOLEAN,
    "sharePercent" DECIMAL(8,4),
    "representedShareGroup" TEXT,
    "isIndependent" BOOLEAN,
    "independenceDisclosure" TEXT,
    "evaluatedByNomCommittee" BOOLEAN,
    "lostIndependence" BOOLEAN,
    "committees" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "board_members_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "executives" (
    "id" SERIAL NOT NULL,
    "companyId" INTEGER NOT NULL,
    "fullName" TEXT NOT NULL,
    "title" TEXT,
    "profession" TEXT,
    "rolesLast5Years" TEXT,
    "externalRoles" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "executives_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "shareholders" (
    "id" SERIAL NOT NULL,
    "companyId" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "shareAmountTL" DECIMAL(20,2),
    "sharePercent" DECIMAL(8,4),
    "votingPercent" DECIMAL(8,4),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "shareholders_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "subsidiaries" (
    "id" SERIAL NOT NULL,
    "companyId" INTEGER NOT NULL,
    "tradeName" TEXT NOT NULL,
    "activity" TEXT,
    "paidInCapital" DECIMAL(20,2),
    "companyShareAmount" DECIMAL(20,2),
    "currency" TEXT,
    "sharePercent" DECIMAL(8,4),
    "relationType" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "subsidiaries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "financial_statements" (
    "id" SERIAL NOT NULL,
    "companyId" INTEGER NOT NULL,
    "year" INTEGER NOT NULL,
    "quarter" INTEGER NOT NULL,
    "itemCode" VARCHAR(32) NOT NULL,
    "itemNameTR" VARCHAR(256) NOT NULL,
    "itemNameEN" VARCHAR(256),
    "value" DECIMAL(20,2),
    "statementType" "StatementType" NOT NULL,
    "financialGroup" VARCHAR(16) NOT NULL,
    "currency" VARCHAR(8) NOT NULL DEFAULT 'TRY',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "financial_statements_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "company_financial_groups" (
    "id" SERIAL NOT NULL,
    "ticker" VARCHAR(16) NOT NULL,
    "financialGroup" VARCHAR(32) NOT NULL,
    "displayName" VARCHAR(128),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "company_financial_groups_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "indices_name_key" ON "indices"("name");

-- CreateIndex
CREATE UNIQUE INDEX "indices_code_key" ON "indices"("code");

-- CreateIndex
CREATE UNIQUE INDEX "main_sectors_name_key" ON "main_sectors"("name");

-- CreateIndex
CREATE UNIQUE INDEX "sub_sectors_name_mainSectorId_key" ON "sub_sectors"("name", "mainSectorId");

-- CreateIndex
CREATE UNIQUE INDEX "markets_name_key" ON "markets"("name");

-- CreateIndex
CREATE UNIQUE INDEX "companies_code_key" ON "companies"("code");

-- CreateIndex
CREATE INDEX "companies_isTradable_idx" ON "companies"("isTradable");

-- CreateIndex
CREATE INDEX "companies_freeFloatTicker_idx" ON "companies"("freeFloatTicker");

-- CreateIndex
CREATE INDEX "financial_statements_companyId_year_quarter_idx" ON "financial_statements"("companyId", "year", "quarter");

-- CreateIndex
CREATE INDEX "financial_statements_companyId_itemCode_idx" ON "financial_statements"("companyId", "itemCode");

-- CreateIndex
CREATE INDEX "financial_statements_statementType_year_quarter_idx" ON "financial_statements"("statementType", "year", "quarter");

-- CreateIndex
CREATE UNIQUE INDEX "financial_statements_companyId_year_quarter_itemCode_key" ON "financial_statements"("companyId", "year", "quarter", "itemCode");

-- CreateIndex
CREATE UNIQUE INDEX "company_financial_groups_ticker_key" ON "company_financial_groups"("ticker");

-- CreateIndex
CREATE INDEX "company_financial_groups_ticker_idx" ON "company_financial_groups"("ticker");

-- AddForeignKey
ALTER TABLE "sub_sectors" ADD CONSTRAINT "sub_sectors_mainSectorId_fkey" FOREIGN KEY ("mainSectorId") REFERENCES "main_sectors"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "companies" ADD CONSTRAINT "companies_mainSectorId_fkey" FOREIGN KEY ("mainSectorId") REFERENCES "main_sectors"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "companies" ADD CONSTRAINT "companies_subSectorId_fkey" FOREIGN KEY ("subSectorId") REFERENCES "sub_sectors"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "company_indices" ADD CONSTRAINT "company_indices_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "company_indices" ADD CONSTRAINT "company_indices_indexId_fkey" FOREIGN KEY ("indexId") REFERENCES "indices"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "company_markets" ADD CONSTRAINT "company_markets_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "company_markets" ADD CONSTRAINT "company_markets_marketId_fkey" FOREIGN KEY ("marketId") REFERENCES "markets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ir_staff" ADD CONSTRAINT "ir_staff_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "board_members" ADD CONSTRAINT "board_members_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "executives" ADD CONSTRAINT "executives_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "shareholders" ADD CONSTRAINT "shareholders_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "subsidiaries" ADD CONSTRAINT "subsidiaries_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "financial_statements" ADD CONSTRAINT "financial_statements_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
