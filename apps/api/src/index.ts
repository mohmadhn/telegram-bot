import express from 'express';
import cors from 'cors';
import { PrismaClient } from '@prisma/client';
import customerRoutes from './routes/customers';

export const prisma = new PrismaClient();

const app = express();
app.use(cors());
app.use(express.json());

app.use('/customers', customerRoutes);

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
