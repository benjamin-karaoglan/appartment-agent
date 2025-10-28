import Link from 'next/link'
import { Home, FileText, Image, TrendingUp, Shield, Calculator } from 'lucide-react'

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      {/* Hero Section */}
      <div className="container mx-auto px-4 py-16">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            Appartment Agent
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Make smarter apartment purchasing decisions with AI-powered insights
          </p>
          <div className="flex gap-4 justify-center">
            <Link href="/auth/register" className="btn-primary text-lg px-8 py-3">
              Get Started
            </Link>
            <Link href="/auth/login" className="btn-secondary text-lg px-8 py-3">
              Sign In
            </Link>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 mt-16">
          <FeatureCard
            icon={<TrendingUp className="w-12 h-12 text-primary-600" />}
            title="Price Analysis"
            description="Compare asking prices with real market data from French DVF records. Know if you're getting a fair deal."
          />
          <FeatureCard
            icon={<FileText className="w-12 h-12 text-primary-600" />}
            title="Document Analysis"
            description="AI-powered analysis of PV d'AG, diagnostics, and financial documents to uncover hidden costs."
          />
          <FeatureCard
            icon={<Shield className="w-12 h-12 text-primary-600" />}
            title="Risk Assessment"
            description="Identify potential issues like amiante, plomb, and poor DPE ratings before you commit."
          />
          <FeatureCard
            icon={<Calculator className="w-12 h-12 text-primary-600" />}
            title="Cost Calculator"
            description="Comprehensive annual cost estimates including charges, taxes, and upcoming works."
          />
          <FeatureCard
            icon={<Image className="w-12 h-12 text-primary-600" />}
            title="Style Visualization"
            description="Upload photos and use AI to visualize renovation potential and style transformations."
          />
          <FeatureCard
            icon={<Home className="w-12 h-12 text-primary-600" />}
            title="Investment Score"
            description="Get a comprehensive investment score and data-driven recommendations for each property."
          />
        </div>

        {/* How It Works */}
        <div className="mt-24">
          <h2 className="text-3xl font-bold text-center mb-12">How It Works</h2>
          <div className="grid md:grid-cols-4 gap-8">
            <Step number="1" title="Enter Address" description="Input the apartment address and basic details" />
            <Step number="2" title="Upload Documents" description="Upload PV d'AG, diagnostics, and financial documents" />
            <Step number="3" title="AI Analysis" description="Our AI analyzes everything and compares with market data" />
            <Step number="4" title="Get Insights" description="Receive comprehensive report and recommendation" />
          </div>
        </div>

        {/* CTA Section */}
        <div className="mt-24 text-center bg-primary-600 text-white rounded-2xl p-12">
          <h2 className="text-3xl font-bold mb-4">Ready to make smarter property decisions?</h2>
          <p className="text-xl mb-8 opacity-90">Join thousands of smart buyers in France</p>
          <Link href="/auth/register" className="bg-white text-primary-600 hover:bg-gray-100 font-medium py-3 px-8 rounded-lg transition-colors inline-block">
            Start Your Free Analysis
          </Link>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-8 mt-16">
        <div className="container mx-auto px-4 text-center">
          <p>&copy; 2025 Appartment Agent. All rights reserved.</p>
          <p className="text-gray-400 mt-2">Helping you make informed property decisions in France</p>
        </div>
      </footer>
    </div>
  )
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) {
  return (
    <div className="card hover:shadow-lg transition-shadow">
      <div className="mb-4">{icon}</div>
      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  )
}

function Step({ number, title, description }: { number: string, title: string, description: string }) {
  return (
    <div className="text-center">
      <div className="w-16 h-16 bg-primary-600 text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
        {number}
      </div>
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  )
}
