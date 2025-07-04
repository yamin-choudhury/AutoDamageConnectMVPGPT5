// Quick database check script
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://urdbbrndqpbhxjfpeafd.supabase.co'
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVyZGJicm5kcXBiaHhqZnBlYWZkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTA4MDI5MzcsImV4cCI6MjA2NjM3ODkzN30.wK3jo0v4Ez1gAfEjxSpnXQ6FQG0LFmRW_2mC3yPK-ho'

const supabase = createClient(supabaseUrl, supabaseKey)

async function checkDatabase() {
  // Skip auth for now and check storage directly
  console.log('Checking Supabase storage for images...')
  
  // List files in the images bucket
  const { data: storageData, error: storageError } = await supabase.storage
    .from('images')
    .list()
    
  console.log('Storage images bucket:')
  console.log('Error:', storageError)
  console.log('Files:', JSON.stringify(storageData, null, 2))
  
  // Also check the reports bucket for JSON reports
  console.log('\nChecking Supabase storage for reports...')
  const { data: reportsData, error: reportsError } = await supabase.storage
    .from('reports')
    .list()
    
  console.log('Storage reports bucket:')
  console.log('Error:', reportsError)
  console.log('Files:', JSON.stringify(reportsData, null, 2))
  
  console.log('\nChecking documents table...')
  
  const { data, error } = await supabase
    .from('documents')
    .select('id, status, report_json, report_pdf_url')
    .limit(5)
  
  console.log('Documents query result:')
  console.log('Error:', error)
  console.log('Data:', JSON.stringify(data, null, 2))
  
  console.log('\nChecking document_images table...')
  const { data: imageData, error: imageError } = await supabase
    .from('document_images')
    .select('*')
    .limit(5)
  
  console.log('Images query result:')
  console.log('Error:', imageError)
  console.log('Data:', JSON.stringify(imageData, null, 2))
  
  // Also check if there's an 'images' table instead
  console.log('\nChecking images table...')
  const { data: imagesData, error: imagesError } = await supabase
    .from('images')
    .select('*')
    .limit(5)
  
  console.log('Images table query result:')
  console.log('Error:', imagesError)
  console.log('Data:', JSON.stringify(imagesData, null, 2))
}

checkDatabase()
