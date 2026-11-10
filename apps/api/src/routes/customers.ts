import { Router } from 'express';
import { prisma } from '../index';

const router = Router();

// GET all customers
router.get('/', async (req, res) => {
  try {
    const customers = await prisma.customer.findMany();
    res.json(customers);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch customers' });
  }
});

// POST new customer
router.post('/', async (req, res) => {
  try {
    const { name, contactInfo } = req.body;
    const customer = await prisma.customer.create({
      data: {
        name,
        contactInfo
      }
    });
    res.status(201).json(customer);
  } catch (error) {
    res.status(500).json({ error: 'Failed to create customer' });
  }
});

export default router;
