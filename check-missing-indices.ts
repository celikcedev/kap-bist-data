import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  const missingTickers = ['ATEKS', 'ATLAS', 'ATSYH', 'AYES', 'BALAT'];

  for (const code of missingTickers) {
    const company = await prisma.company.findUnique({
      where: { code }
    });

    if (!company) {
      console.log(`❌ ${code}: Şirket bulunamadı!`);
      continue;
    }

    const indices = await prisma.companyIndex.findMany({
      where: { companyId: company.id },
      include: { index: true }
    });

    console.log(`\n📌 ${code} (${company.name}):`);
    console.log(`   Tradable: ${company.isTradable}`);
    console.log(`   Endeksler: ${indices.length === 0 ? 'YOK' : ''}`);
    indices.forEach(ci => {
      console.log(`     - ${ci.index.name}`);
    });
  }

  await prisma.$disconnect();
}

main().catch(console.error);
