-- S001: synthetic demo data. Idempotent (deterministic ids + ON DUPLICATE KEY UPDATE). Educational use only.
-- Users and pharmacist_assignments are inserted by scripts/seed.py first (they need password hashes).

INSERT INTO pharmacies (id, name, city, address) VALUES
 (1, 'City Care Pharmacy',  'Bengaluru', '12 Demo Street'),
 (2, 'Green Cross Pharmacy', 'Bengaluru', '45 Sample Road'),
 (3, 'Lakeside Pharmacy',   'Mysuru',    '7 Example Lane')
AS n ON DUPLICATE KEY UPDATE name = n.name, city = n.city, address = n.address;

INSERT INTO medicine_categories (id, name, parent_id) VALUES
 (1, 'Pharmaceuticals', NULL),
 (2, 'Analgesics', 1), (3, 'Antipyretic analgesics', 2), (4, 'NSAIDs', 2),
 (5, 'Anti-infectives', 1), (6, 'Antibiotics', 5),
 (7, 'Gastrointestinal', 1), (8, 'Acid reducers', 7),
 (9, 'Respiratory and allergy', 1), (10, 'Antihistamines', 9),
 (11, 'Antidiabetics', 1), (12, 'Biguanides', 11)
AS n ON DUPLICATE KEY UPDATE name = n.name, parent_id = n.parent_id;

INSERT INTO active_ingredients (id, name) VALUES
 (1, 'Paracetamol'), (2, 'Caffeine'), (3, 'Ibuprofen'), (4, 'Amoxicillin'),
 (5, 'Cetirizine'), (6, 'Omeprazole'), (7, 'Metformin'), (8, 'Aspirin')
AS n ON DUPLICATE KEY UPDATE name = n.name;

INSERT INTO medicines (id, name, brand, category_id, dosage_form, route, release_type, strength_basis,
                       requires_prescription, substitution_allowed, is_active) VALUES
 (1,  'Paracetamol 500 mg Tablet',              'Generic',     3,  'tablet',  'oral', 'immediate', 'per tablet',  0, 1, 1),
 (2,  'Pyrelief 500 Tablet',                    'Medico Labs', 3,  'tablet',  'oral', 'immediate', 'per tablet',  0, 1, 1),
 (3,  'Febrix 500 Tablet',                      'Nova Pharma', 3,  'tablet',  'oral', 'immediate', 'per tablet',  0, 1, 1),
 (4,  'Paracetamol 650 mg Tablet',              'Generic',     3,  'tablet',  'oral', 'immediate', 'per tablet',  0, 1, 1),
 (5,  'Paracetamol + Caffeine Tablet',          'Medico Labs', 3,  'tablet',  'oral', 'immediate', 'per tablet',  0, 1, 1),
 (6,  'Paracetamol Oral Syrup 250 mg/5 ml',     'Generic',     3,  'syrup',   'oral', 'immediate', 'per 5 ml',    0, 1, 1),
 (7,  'Paracetamol 500 mg ER Tablet',           'Nova Pharma', 3,  'tablet',  'oral', 'extended',  'per tablet',  0, 1, 1),
 (8,  'Parasprin 500 Tablet',                   'Nova Pharma', 3,  'tablet',  'oral', 'immediate', 'per tablet',  0, 1, 1),
 (9,  'Ibuprofen 400 mg Tablet',                'Generic',     4,  'tablet',  'oral', 'immediate', 'per tablet',  0, 1, 1),
 (10, 'Ibufen 400 Tablet',                      'Medico Labs', 4,  'tablet',  'oral', 'immediate', 'per tablet',  0, 1, 1),
 (11, 'Amoxicillin 500 mg Capsule',             'Generic',     6,  'capsule', 'oral', 'immediate', 'per capsule', 1, 1, 1),
 (12, 'Amoxyl 500 Capsule',                     'Nova Pharma', 6,  'capsule', 'oral', 'immediate', 'per capsule', 1, 1, 1),
 (13, 'Cetirizine 10 mg Tablet',                'Generic',     10, 'tablet',  'oral', 'immediate', 'per tablet',  0, 1, 1),
 (14, 'Omeprazole 20 mg Capsule',               'Generic',     8,  'capsule', 'oral', 'immediate', 'per capsule', 0, 1, 1),
 (15, 'Metformin 500 mg Tablet',                'Generic',     12, 'tablet',  'oral', 'immediate', 'per tablet',  1, 1, 1),
 (16, 'Metformin 500 mg Tablet (Brand B)',      'Nova Pharma', 12, 'tablet',  'oral', 'immediate', 'per tablet',  1, 0, 1),
 (17, 'Paracetamol 500 mg Tablet (Discontinued)', 'Generic',   3,  'tablet',  'oral', 'immediate', 'per tablet',  0, 1, 0)
AS n ON DUPLICATE KEY UPDATE name = n.name, brand = n.brand, category_id = n.category_id, dosage_form = n.dosage_form,
  route = n.route, release_type = n.release_type, strength_basis = n.strength_basis,
  requires_prescription = n.requires_prescription, substitution_allowed = n.substitution_allowed, is_active = n.is_active;

INSERT INTO medicine_ingredients (medicine_id, ingredient_id, strength_mg) VALUES
 (1,1,500), (2,1,500), (3,1,500), (4,1,650), (5,1,500), (5,2,30), (6,1,250), (7,1,500), (8,8,500),
 (9,3,400), (10,3,400), (11,4,500), (12,4,500), (13,5,10), (14,6,20), (15,7,500), (16,7,500), (17,1,500)
AS n ON DUPLICATE KEY UPDATE strength_mg = n.strength_mg;

INSERT INTO shortage_entries (id, medicine_id, status, severity, reported_at, resolved_at, source, note) VALUES
 (1, 3,  'OPEN',     'HIGH',   '2026-09-20 09:00:00', NULL, 'demo', 'Synthetic: supplier delay'),
 (2, 12, 'OPEN',     'MEDIUM', '2026-10-01 10:30:00', NULL, 'demo', 'Synthetic: low regional supply'),
 (3, 7,  'RESOLVED', 'LOW',    '2026-08-15 08:00:00', '2026-09-05 12:00:00', 'demo', 'Synthetic: restocked')
AS n ON DUPLICATE KEY UPDATE status = n.status, severity = n.severity, reported_at = n.reported_at,
  resolved_at = n.resolved_at, note = n.note;

-- Stock states: In stock / Low (qty <= reorder_level) / Out (0) across the three pharmacies.
-- Inserting or updating a row fires the low-stock triggers, which create the matching alerts.
INSERT INTO inventory (pharmacy_id, medicine_id, quantity, reorder_level) VALUES
 (1,1,120,30),(1,2,8,20),(1,3,0,20),(1,4,50,10),(1,5,40,10),(1,6,25,10),(1,7,0,10),(1,8,60,10),
 (1,9,100,20),(1,10,15,20),(1,11,70,20),(1,12,0,20),(1,13,90,20),(1,14,45,15),(1,15,30,10),
 (2,1,0,30),(2,2,80,20),(2,3,0,20),(2,4,20,10),(2,7,12,10),(2,8,40,10),(2,9,0,20),(2,10,55,20),
 (2,11,5,20),(2,12,30,20),(2,13,25,10),(2,14,0,15),(2,15,60,10),
 (3,1,15,30),(3,2,0,20),(3,3,0,20),(3,5,22,10),(3,9,35,20),(3,10,0,20),(3,11,0,20),(3,13,0,10),(3,14,60,15)
AS n ON DUPLICATE KEY UPDATE quantity = n.quantity, reorder_level = n.reorder_level;

INSERT INTO orders (id, patient_id, pharmacy_id, status, prescription_note) VALUES
 (1, 4, 1, 'REQUESTED',    NULL),
 (2, 5, 2, 'UNDER_REVIEW', NULL),
 (3, 4, 1, 'APPROVED',     NULL),
 (4, 5, 2, 'COMPLETED',    NULL),
 (5, 4, 1, 'REJECTED',     'Synthetic note: unclear handwriting')
ON DUPLICATE KEY UPDATE id = id;

INSERT INTO order_items (id, order_id, requested_medicine_id, dispensed_medicine_id, quantity) VALUES
 (1, 1, 1,  NULL, 10),
 (2, 2, 1,  NULL, 5),
 (3, 3, 2,  2,    2),
 (4, 4, 10, 10,   4),
 (5, 5, 11, NULL, 3)
ON DUPLICATE KEY UPDATE id = id;
