import { z } from 'zod';

export const RequirementSchema = z.object({
  features: z.array(z.string()),
  constraints: z.array(z.string()),
  missingInformation: z.array(z.string()),
});

export type Requirement = z.infer<typeof RequirementSchema>;