DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'sale_items'
  ) THEN
    CREATE TABLE sale_items (
      id SERIAL PRIMARY KEY,
      sale_id INTEGER REFERENCES sales (id),
      description varchar(255),
      hsn_sac varchar(12),
      qty numeric(12,3) DEFAULT 1,
      rate numeric(12,2) DEFAULT 0,
      gst_rate numeric(5,2) DEFAULT 0,
      tax_rate numeric(5,2) DEFAULT 0,
      line_total numeric(12,2) DEFAULT 0
    );
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'sales' AND column_name = 'subtotal'
  ) THEN
    ALTER TABLE sales
      ADD COLUMN subtotal numeric(12,2) DEFAULT 0,
      ADD COLUMN tax_total numeric(12,2) DEFAULT 0,
      ADD COLUMN roundoff numeric(12,2) DEFAULT 0,
      ADD COLUMN cgst numeric(12,2) DEFAULT 0,
      ADD COLUMN sgst numeric(12,2) DEFAULT 0,
      ADD COLUMN igst numeric(12,2) DEFAULT 0,
      ADD COLUMN seller_gstin varchar(20),
      ADD COLUMN buyer_gstin varchar(20),
      ADD COLUMN seller_state varchar(32),
      ADD COLUMN buyer_state varchar(32),
      ADD COLUMN place_of_supply varchar(32),
      ADD COLUMN notes text;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'sale_items' AND column_name = 'hsn_sac'
  ) THEN
    ALTER TABLE sale_items
      ADD COLUMN hsn_sac varchar(12),
      ADD COLUMN gst_rate numeric(5,2) DEFAULT 0,
      ADD COLUMN tax_rate numeric(5,2) DEFAULT 0,
      ADD COLUMN line_total numeric(12,2) DEFAULT 0;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'customers' AND column_name = 'state'
  ) THEN
    ALTER TABLE customers
      ADD COLUMN state varchar(32);
  END IF;
END
$$;
