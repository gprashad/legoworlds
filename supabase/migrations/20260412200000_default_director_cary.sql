ALTER TABLE scenes ALTER COLUMN director_name SET DEFAULT 'Cary';
UPDATE scenes SET director_name = 'Cary' WHERE director_name = 'Jackson';
