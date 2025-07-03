
-- Create profiles table for user data
CREATE TABLE public.profiles (
  id UUID NOT NULL REFERENCES auth.users ON DELETE CASCADE,
  email TEXT,
  full_name TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  PRIMARY KEY (id)
);

-- Create documents table for storing document generation history
CREATE TABLE public.documents (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT 'Untitled Document',
  vin TEXT,
  registration_plate TEXT,
  make TEXT,
  model TEXT,
  year TEXT,
  trim_body_style TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create document_images table for storing uploaded images
CREATE TABLE public.document_images (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  document_id UUID NOT NULL REFERENCES public.documents ON DELETE CASCADE,
  image_url TEXT NOT NULL,
  image_name TEXT NOT NULL,
  file_size INTEGER,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_images ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for profiles
CREATE POLICY "Users can view their own profile" 
  ON public.profiles 
  FOR SELECT 
  USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile" 
  ON public.profiles 
  FOR UPDATE 
  USING (auth.uid() = id);

CREATE POLICY "Users can insert their own profile" 
  ON public.profiles 
  FOR INSERT 
  WITH CHECK (auth.uid() = id);

-- Create RLS policies for documents
CREATE POLICY "Users can view their own documents" 
  ON public.documents 
  FOR SELECT 
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create their own documents" 
  ON public.documents 
  FOR INSERT 
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own documents" 
  ON public.documents 
  FOR UPDATE 
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own documents" 
  ON public.documents 
  FOR DELETE 
  USING (auth.uid() = user_id);

-- Create RLS policies for document_images
CREATE POLICY "Users can view images of their own documents" 
  ON public.document_images 
  FOR SELECT 
  USING (EXISTS (
    SELECT 1 FROM public.documents 
    WHERE documents.id = document_images.document_id 
    AND documents.user_id = auth.uid()
  ));

CREATE POLICY "Users can create images for their own documents" 
  ON public.document_images 
  FOR INSERT 
  WITH CHECK (EXISTS (
    SELECT 1 FROM public.documents 
    WHERE documents.id = document_images.document_id 
    AND documents.user_id = auth.uid()
  ));

CREATE POLICY "Users can delete images of their own documents" 
  ON public.document_images 
  FOR DELETE 
  USING (EXISTS (
    SELECT 1 FROM public.documents 
    WHERE documents.id = document_images.document_id 
    AND documents.user_id = auth.uid()
  ));

-- Create trigger function to handle new user profiles
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data ->> 'full_name', NEW.raw_user_meta_data ->> 'name', split_part(NEW.email, '@', 1))
  );
  RETURN NEW;
END;
$$;

-- Create trigger to automatically create profile on user signup
CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
