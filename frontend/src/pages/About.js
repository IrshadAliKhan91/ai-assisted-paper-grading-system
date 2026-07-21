import React from 'react';
import { Brain, ScanLine, Database, FileText, Shield, Zap, Users, Award, GraduationCap } from 'lucide-react';
import './About.css';

function About() {
  return (
    <div className="about-page">
      {/* Hero */}
      <section className="about-hero">
        <div className="about-badge">
          <GraduationCap size={14} />
          Final Year Project — 2026
        </div>
        <h1 className="about-title">About FairMark</h1>
        <p className="about-desc">
          An AI-powered paper grading system that combines Optical Character
          Recognition with Natural Language Processing to deliver fast, accurate,
          and unbiased assessment of handwritten answer sheets.
        </p>
      </section>

      {/* Mission */}
      <section className="about-section">
        <h2 className="section-title">Our Mission</h2>
        <div className="mission-card">
          <p>
            Traditional paper grading is time-consuming, subjective, and prone to
            human error. FairMark was built to solve these problems by leveraging
            modern AI techniques — giving educators a tool that is <strong>fair</strong>,
            <strong> consistent</strong>, and <strong>transparent</strong> in every assessment.
          </p>
        </div>
      </section>

      {/* How It Works */}
      <section className="about-section">
        <h2 className="section-title">How It Works</h2>
        <div className="pipeline-grid">
          <PipelineCard
            icon={<ScanLine size={28} />}
            step="1"
            title="OCR Extraction"
            description="Vision AI and fallback OCR scans uploaded answer sheets, detects student info, and segments individual question–answer pairs."
          />
          <PipelineCard
            icon={<Brain size={28} />}
            step="2"
            title="NLP Grading"
            description="Sentence-BERT embeddings compute semantic similarity between student answers and correct answers stored in the question bank."
          />
          <PipelineCard
            icon={<Database size={28} />}
            step="3"
            title="Score & Store"
            description="Marks are assigned on a 0–10 scale per question. All submissions, scores, and metadata are persisted in a PostgreSQL database."
          />
          <PipelineCard
            icon={<FileText size={28} />}
            step="4"
            title="Report & Export"
            description="Detailed result breakdowns with AI similarity scores are displayed on-screen and can be exported as professional PDF reports."
          />
        </div>
      </section>

      {/* Features */}
      <section className="about-section">
        <h2 className="section-title">Key Features</h2>
        <div className="features-grid">
          <FeatureCard
            icon={<Zap size={20} />}
            title="Instant Grading"
            description="Grade a full answer sheet in under 30 seconds with AI-powered analysis."
          />
          <FeatureCard
            icon={<Shield size={20} />}
            title="Fair & Unbiased"
            description="Semantic similarity scoring eliminates human bias and ensures consistent evaluation."
          />
          <FeatureCard
            icon={<Database size={20} />}
            title="Custom Answer Keys"
            description="Teachers can upload their own question banks for subject-specific grading."
          />
          <FeatureCard
            icon={<FileText size={20} />}
            title="PDF Reports"
            description="Export detailed grading reports with question-wise breakdowns and scores."
          />
          <FeatureCard
            icon={<Users size={20} />}
            title="Student Records"
            description="Search and track student performance across multiple submissions."
          />
          <FeatureCard
            icon={<Award size={20} />}
            title="Analytics Dashboard"
            description="Visualize class performance, subject trends, and top performers at a glance."
          />
        </div>
      </section>

      {/* Tech Stack */}
      <section className="about-section">
        <h2 className="section-title">Technology Stack</h2>
        <div className="stack-grid">
          <StackItem label="Frontend" value="React 18" />
          <StackItem label="Backend" value="FastAPI (Python)" />
          <StackItem label="Database" value="PostgreSQL / SQLite" />
          <StackItem label="OCR Engine" value="Molmo Vision AI & RapidAPI" />
          <StackItem label="NLP Model" value="Sentence-BERT (all-MiniLM)" />
          <StackItem label="Styling" value="Custom CSS Design System" />
        </div>
      </section>

      {/* Team */}
      <section className="about-section">
        <h2 className="section-title">Project Team</h2>
        <div className="team-grid">
          <TeamCard name="Irshad Ali Khan" role="Developer" />
          <TeamCard name="Sadiq Mansoor" role="Developer" />
          <TeamCard name="Wisal Ahmad" role="Developer" />
        </div>
      </section>


    </div>
  );
}


function PipelineCard({ icon, step, title, description }) {
  return (
    <div className="pipeline-card">
      <div className="pipeline-step">{step}</div>
      <div className="pipeline-icon">{icon}</div>
      <h3 className="pipeline-title">{title}</h3>
      <p className="pipeline-desc">{description}</p>
    </div>
  );
}

function FeatureCard({ icon, title, description }) {
  return (
    <div className="feature-card">
      <div className="feature-icon">{icon}</div>
      <h3 className="feature-title">{title}</h3>
      <p className="feature-desc">{description}</p>
    </div>
  );
}

function StackItem({ label, value }) {
  return (
    <div className="stack-item">
      <span className="stack-label">{label}</span>
      <span className="stack-value">{value}</span>
    </div>
  );
}

function TeamCard({ name, role }) {
  return (
    <div className="team-card">
      <div className="team-avatar">
        {name.split(' ').map(w => w[0]).join('')}
      </div>
      <p className="team-name">{name}</p>
      <p className="team-role">{role}</p>
    </div>
  );
}

export default About;
