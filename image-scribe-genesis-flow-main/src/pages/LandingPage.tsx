import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Car, Shield, Clock, BarChart3, Users, Award, CheckCircle2, ArrowRight, Building2 } from "lucide-react";

const LandingPage = () => {
  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="bg-white border-b border-gray-100 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <Car className="h-8 w-8 text-blue-600 mr-3" />
              <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-blue-800 bg-clip-text text-transparent">
                AutoDamageConnect
              </span>
            </div>
            <div className="flex items-center space-x-4">
              <Link to="/auth">
                <Button variant="ghost" className="text-gray-600 hover:text-blue-600">
                  Sign In
                </Button>
              </Link>
              <Link to="/auth">
                <Button className="bg-blue-600 hover:bg-blue-700 text-white">
                  Start Free Trial
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 text-white overflow-hidden">
        <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:60px_60px]" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 lg:py-32">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-8">
              <div className="inline-flex items-center bg-blue-600/10 border border-blue-400/20 rounded-full px-4 py-2 text-blue-300 text-sm">
                <Award className="w-4 h-4 mr-2" />
                Trusted by leading insurers across the UK
              </div>
              <h1 className="text-5xl lg:text-6xl font-bold leading-tight">
                Transform Vehicle 
                <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                  Damage Assessment
                </span>
              </h1>
              <p className="text-xl text-gray-300 leading-relaxed max-w-2xl">
                Enterprise-grade AI platform delivering instant, precise vehicle damage analysis. 
                Reduce claim processing time by 85% whilst maintaining forensic accuracy standards.
              </p>
              <div className="flex flex-col sm:flex-row gap-4">
                <Link to="/auth">
                  <Button size="lg" className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 text-lg rounded-lg shadow-xl">
                    Start Free Enterprise Trial
                    <ArrowRight className="ml-2 h-5 w-5" />
                  </Button>
                </Link>
                <Button size="lg" variant="outline" className="border-2 border-gray-600 text-white hover:bg-white hover:text-gray-900 px-8 py-4 text-lg rounded-lg">
                  Schedule Demo
                </Button>
              </div>
            </div>
            <div className="relative">
              <div className="bg-gradient-to-r from-blue-600 to-cyan-600 rounded-2xl p-8 shadow-2xl">
                <div className="bg-white rounded-lg p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-600">Damage Assessment Report</span>
                    <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">Complete</span>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-700">Vehicle:</span>
                      <span className="font-medium">2023 BMW X5</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-700">Analysis Time:</span>
                      <span className="font-medium text-blue-600">2.3 seconds</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-700">Damage Severity:</span>
                      <span className="font-medium text-orange-600">Moderate</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-700">Repair Estimate:</span>
                      <span className="font-medium text-green-600">£3,250</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8 text-center">
            <div>
              <div className="text-4xl font-bold text-blue-600 mb-2">£2.3B+</div>
              <div className="text-gray-600">Claims Processed</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-blue-600 mb-2">98.7%</div>
              <div className="text-gray-600">Accuracy Rate</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-blue-600 mb-2">150+</div>
              <div className="text-gray-600">Enterprise Clients</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-blue-600 mb-2">85%</div>
              <div className="text-gray-600">Time Reduction</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Built for Enterprise Insurance Operations
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Comprehensive AI-driven platform designed specifically for UK insurers, 
              repairers, and automotive professionals requiring forensic-grade accuracy.
            </p>
          </div>
          <div className="grid lg:grid-cols-3 gap-8">
            <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-lg hover:shadow-xl transition-shadow">
              <Shield className="text-blue-600 mb-6" size={48} />
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Forensic Accuracy</h3>
              <p className="text-gray-600 mb-4">
                Computer vision trained on 2M+ UK insurance claims. Meets FCA compliance standards 
                with full audit trails and expert witness-grade documentation.
              </p>
              <ul className="space-y-2 text-sm text-gray-600">
                <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-green-500 mr-2" />ISO 27001 certified</li>
                <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-green-500 mr-2" />GDPR compliant</li>
                <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-green-500 mr-2" />Expert witness reports</li>
              </ul>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-lg hover:shadow-xl transition-shadow">
              <Clock className="text-green-600 mb-6" size={48} />
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Instant Processing</h3>
              <p className="text-gray-600 mb-4">
                Transform weeks of manual assessment into seconds. Real-time damage detection, 
                parts identification, and repair cost estimation with 99.2% uptime SLA.
              </p>
              <ul className="space-y-2 text-sm text-gray-600">
                <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-green-500 mr-2" />2.3 second analysis</li>
                <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-green-500 mr-2" />24/7 API availability</li>
                <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-green-500 mr-2" />Real-time notifications</li>
              </ul>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-lg hover:shadow-xl transition-shadow">
              <Building2 className="text-purple-600 mb-6" size={48} />
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Enterprise Integration</h3>
              <p className="text-gray-600 mb-4">
                Seamlessly integrates with existing claims management systems. 
                White-label solutions available with full API access and custom branding.
              </p>
              <ul className="space-y-2 text-sm text-gray-600">
                <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-green-500 mr-2" />RESTful API</li>
                <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-green-500 mr-2" />White-label ready</li>
                <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-green-500 mr-2" />Custom integrations</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Industry Leadership Section */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Trusted by Industry Leaders
            </h2>
            <p className="text-xl text-gray-600">
              Leading UK insurers, repairers, and fleet operators rely on AutoDamageConnect
            </p>
          </div>
          <div className="grid lg:grid-cols-3 gap-8 mb-16">
            <div className="text-center">
              <div className="bg-blue-100 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <Shield className="w-8 h-8 text-blue-600" />
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">Major Insurers</h3>
              <p className="text-gray-600">Aviva, AXA, Admiral, and 40+ other leading insurers</p>
            </div>
            <div className="text-center">
              <div className="bg-green-100 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <Users className="w-8 h-8 text-green-600" />
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">Approved Repairers</h3>
              <p className="text-gray-600">500+ BSI Kitemark approved body shops nationwide</p>
            </div>
            <div className="text-center">
              <div className="bg-purple-100 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <BarChart3 className="w-8 h-8 text-purple-600" />
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">Fleet Operators</h3>
              <p className="text-gray-600">Enterprise fleets managing 100,000+ vehicles</p>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              What Industry Leaders Say
            </h2>
          </div>
          <div className="grid lg:grid-cols-3 gap-8">
            <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-lg">
              <div className="flex items-center mb-4">
                <div className="flex text-yellow-400">
                  {'★'.repeat(5)}
                </div>
              </div>
              <blockquote className="text-gray-600 mb-6">
                "AutoDamageConnect has revolutionised our claims processing. 85% faster assessments with forensic accuracy. ROI achieved within 3 months."
              </blockquote>
              <div className="flex items-center">
                <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold mr-4">
                  SM
                </div>
                <div>
                  <div className="font-semibold text-gray-900">Sarah Mitchell</div>
                  <div className="text-gray-600 text-sm">Head of Claims, Major UK Insurer</div>
                </div>
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-lg">
              <div className="flex items-center mb-4">
                <div className="flex text-yellow-400">
                  {'★'.repeat(5)}
                </div>
              </div>
              <blockquote className="text-gray-600 mb-6">
                "The forensic-grade accuracy and compliance features make this essential for our approved repairer network. Game-changing technology."
              </blockquote>
              <div className="flex items-center">
                <div className="w-12 h-12 bg-green-600 rounded-full flex items-center justify-center text-white font-bold mr-4">
                  DT
                </div>
                <div>
                  <div className="font-semibold text-gray-900">David Thompson</div>
                  <div className="text-gray-600 text-sm">Managing Director, Elite Body Shop Group</div>
                </div>
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-lg">
              <div className="flex items-center mb-4">
                <div className="flex text-yellow-400">
                  {'★'.repeat(5)}
                </div>
              </div>
              <blockquote className="text-gray-600 mb-6">
                "Managing fleet damage assessments for 50,000 vehicles is now seamless. The API integration and white-label solution are exceptional."
              </blockquote>
              <div className="flex items-center">
                <div className="w-12 h-12 bg-purple-600 rounded-full flex items-center justify-center text-white font-bold mr-4">
                  RH
                </div>
                <div>
                  <div className="font-semibold text-gray-900">Rachel Hughes</div>
                  <div className="text-gray-600 text-sm">Fleet Operations Director, FTSE 100 Company</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Enterprise CTA Section */}
      <section className="py-20 bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 text-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-4xl lg:text-5xl font-bold mb-6">
            Ready to Transform Your Claims Process?
          </h2>
          <p className="text-xl text-gray-300 mb-8 max-w-2xl mx-auto">
            Join the UK's leading insurers and repairers already reducing claim processing time by 85% 
            whilst maintaining forensic accuracy standards.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/auth">
              <Button size="lg" className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 text-lg rounded-lg">
                Start Enterprise Trial
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
            <Button size="lg" variant="outline" className="border-2 border-gray-600 text-white hover:bg-white hover:text-gray-900 px-8 py-4 text-lg rounded-lg">
              Request Demo
            </Button>
          </div>
          <p className="text-sm text-gray-400 mt-6">
            No setup fees • 30-day free trial • Cancel anytime
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-300">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid lg:grid-cols-4 gap-8">
            <div className="lg:col-span-2">
              <div className="flex items-center mb-4">
                <Car className="h-8 w-8 text-blue-400 mr-3" />
                <span className="text-xl font-bold text-white">AutoDamageConnect</span>
              </div>
              <p className="text-gray-400 mb-4 max-w-md">
                Enterprise-grade AI platform for vehicle damage assessment. 
                Trusted by leading UK insurers and approved repairers.
              </p>
              <div className="text-sm text-gray-500">
                <p>FCA Authorised • ISO 27001 Certified • GDPR Compliant</p>
              </div>
            </div>
            <div>
              <h3 className="text-white font-semibold mb-4">Solutions</h3>
              <ul className="space-y-2 text-gray-400">
                <li>Insurance Claims</li>
                <li>Fleet Management</li>
                <li>Body Shop Operations</li>
                <li>Expert Witness Reports</li>
              </ul>
            </div>
            <div>
              <h3 className="text-white font-semibold mb-4">Company</h3>
              <ul className="space-y-2 text-gray-400">
                <li>About Us</li>
                <li>Careers</li>
                <li>Privacy Policy</li>
                <li>Terms of Service</li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 mt-12 pt-8 text-center text-sm text-gray-500">
            <p>&copy; {new Date().getFullYear()} AutoDamageConnect Ltd. All rights reserved. Registered in England & Wales.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
