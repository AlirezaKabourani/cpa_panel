export type Customer = {
  id: string;
  code: string;
  name: string;
  service_id: string;
  created_at: string;
};

export type CustomerMessage = {
  id: string;
  title?: string | null;
  text_template: string;
  created_at: string;
  is_active: boolean;
};

export type CustomerMedia = {
  id: string;
  file_id: string;
  file_name?: string | null;
  file_type?: string | null;
  created_at: string;
};
