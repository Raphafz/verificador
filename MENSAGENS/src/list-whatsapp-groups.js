import "dotenv/config";
import { connectWhatsApp, listGroups } from "./whatsapp.js";

console.log("Conectando ao WhatsApp para listar grupos...\n");

await connectWhatsApp();
const groups = await listGroups();

if (groups.length === 0) {
  console.log("Nenhum grupo encontrado. Crie o grupo de teste e tente de novo.");
  process.exit(0);
}

console.log("Grupos disponíveis:\n");
for (const g of groups.sort((a, b) => a.name.localeCompare(b.name))) {
  console.log(`  ${g.name}`);
  console.log(`  WHATSAPP_GROUP_JID=${g.jid}\n`);
}

console.log("Copie o JID do grupo de teste para o arquivo .env");
process.exit(0);
