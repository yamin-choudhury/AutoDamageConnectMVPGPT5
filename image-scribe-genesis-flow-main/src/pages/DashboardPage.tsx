import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { User, Session } from "@supabase/supabase-js";
import Dashboard from "@/components/Dashboard";

const DashboardPage = () => {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const clearSupabaseAuth = () => {
    try {
      if (typeof localStorage !== 'undefined') {
        // Remove all Supabase auth tokens regardless of project ref
        Object.keys(localStorage)
          .filter((k) => k.startsWith('sb-') && k.endsWith('-auth-token'))
          .forEach((k) => localStorage.removeItem(k));
      }
      if (typeof sessionStorage !== 'undefined') {
        Object.keys(sessionStorage)
          .filter((k) => k.startsWith('sb-') && k.endsWith('-auth-token'))
          .forEach((k) => sessionStorage.removeItem(k));
      }
    } catch { /* ignore */ }
  };

  useEffect(() => {
    // Set up auth state listener
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        setSession(session);
        setUser(session?.user ?? null);
        setLoading(false);
        
        // Redirect to /auth if not authenticated; also clear any stale tokens
        if (!session) {
          clearSupabaseAuth();
          navigate('/auth');
        }
      }
    );

    // Check for existing session
    supabase.auth.getSession()
      .then(async ({ data: { session } }) => {
        setSession(session);
        setUser(session?.user ?? null);
        setLoading(false);

        // Redirect to /auth if not authenticated; also clear any stale tokens
        if (!session) {
          clearSupabaseAuth();
          try { await supabase.auth.signOut(); } catch { /* ignore */ }
          navigate('/auth');
        }
      })
      .catch(async () => {
        // On any auth error, hard reset auth and redirect
        clearSupabaseAuth();
        try { await supabase.auth.signOut(); } catch { /* ignore */ }
        setSession(null);
        setUser(null);
        setLoading(false);
        navigate('/auth');
      });

    return () => subscription.unsubscribe();
  }, [navigate]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    clearSupabaseAuth();
    navigate('/auth');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-purple-50">
        <div className="text-lg text-gray-600">Loading...</div>
      </div>
    );
  }

  if (!user || !session) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-purple-50">
        <div className="text-lg text-gray-600">Redirecting...</div>
      </div>
    );
  }

  return <Dashboard user={user} onLogout={handleLogout} />;
};

export default DashboardPage;
