-- AI-Powered Community Matching System - Database Setup
-- Run this after creating the database: CREATE DATABASE community_matching;

-- Drop existing tables if they exist (for clean setup)
DROP TABLE IF EXISTS community_activity CASCADE;
DROP TABLE IF EXISTS community_members CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS communities CASCADE;

-- Communities table
CREATE TABLE communities (
    community_id TEXT PRIMARY KEY,
    community_name TEXT NOT NULL,
    category TEXT NOT NULL,
    city TEXT NOT NULL,
    timezone TEXT NOT NULL,
    member_count INTEGER DEFAULT 0,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Community members table
CREATE TABLE community_members (
    user_id TEXT NOT NULL,
    community_id TEXT NOT NULL,
    joined_at TIMESTAMP DEFAULT NOW(),
    auto_joined BOOLEAN DEFAULT false,
    PRIMARY KEY (user_id, community_id),
    FOREIGN KEY (community_id) REFERENCES communities(community_id) ON DELETE CASCADE
);

-- Community activity table
CREATE TABLE community_activity (
    message_id TEXT PRIMARY KEY,
    community_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (community_id) REFERENCES communities(community_id) ON DELETE CASCADE
);

-- Users table
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    bio TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX idx_communities_location ON communities(city, timezone);
CREATE INDEX idx_communities_active ON communities(is_active, member_count DESC);
CREATE INDEX idx_activity_recent ON community_activity(community_id, created_at DESC);
CREATE INDEX idx_activity_user ON community_activity(user_id, created_at DESC);
CREATE INDEX idx_members_community ON community_members(community_id);

-- Insert sample communities for testing
INSERT INTO communities (community_id, community_name, category, city, timezone, member_count, description, is_active) VALUES
-- San Francisco - Programming/AI
('comm_py_sf_001', 'Python Developers SF', 'Programming', 'San Francisco', 'America/Los_Angeles', 1250, 'Community for Python enthusiasts and professionals in the Bay Area', true),
('comm_ai_sf_001', 'AI/ML Researchers SF', 'AI', 'San Francisco', 'America/Los_Angeles', 890, 'Machine learning and AI research community', true),
('comm_js_sf_001', 'JavaScript Guild SF', 'Programming', 'San Francisco', 'America/Los_Angeles', 1100, 'Full-stack JavaScript developers', true),
('comm_ds_sf_001', 'Data Science Hub SF', 'Data Science', 'San Francisco', 'America/Los_Angeles', 1500, 'Data scientists and analysts community', true),
('comm_game_sf_001', 'SF Gaming Community', 'Gaming', 'San Francisco', 'America/Los_Angeles', 3200, 'Casual and competitive gamers', true),

-- New York - Various
('comm_web_ny_001', 'Web Dev NYC', 'Programming', 'New York', 'America/New_York', 2100, 'Full-stack web developers in NYC', true),
('comm_ai_ny_001', 'NYC AI Enthusiasts', 'AI', 'New York', 'America/New_York', 750, 'AI and deep learning community', true),
('comm_data_ny_001', 'Data Science NYC', 'Data Science', 'New York', 'America/New_York', 1800, 'NYC data professionals', true),
('comm_game_ny_001', 'NYC Gamers', 'Gaming', 'New York', 'America/New_York', 2500, 'Gaming community in NYC', true),

-- Austin - Tech
('comm_tech_aus_001', 'Austin Tech Hub', 'Programming', 'Austin', 'America/Chicago', 950, 'General tech community in Austin', true),
('comm_startup_aus_001', 'Austin Startups', 'Business', 'Austin', 'America/Chicago', 1200, 'Startup founders and entrepreneurs', true),

-- Seattle - Various
('comm_py_sea_001', 'Seattle Python Users', 'Programming', 'Seattle', 'America/Los_Angeles', 880, 'Python developers in Seattle', true),
('comm_cloud_sea_001', 'Cloud Engineers Seattle', 'DevOps', 'Seattle', 'America/Los_Angeles', 1100, 'Cloud infrastructure and DevOps', true),

-- Popular communities (for fallback)
('comm_general_001', 'Tech Enthusiasts Global', 'General', 'San Francisco', 'America/Los_Angeles', 5000, 'General tech discussions', true),
('comm_general_002', 'Programming 101', 'Programming', 'San Francisco', 'America/Los_Angeles', 4500, 'Beginner-friendly programming community', true);

-- Insert sample users
INSERT INTO users (user_id, username, bio) VALUES
('user_001', 'alice_ml', 'Senior Python developer specializing in machine learning and neural networks. Love discussing transformer architectures.'),
('user_002', 'bob_fullstack', 'Full-stack developer working with React and Node.js. Always learning new frameworks.'),
('user_003', 'charlie_data', 'Data scientist passionate about statistical analysis and visualization. Python and R enthusiast.'),
('user_004', 'diana_gamer', 'Casual gamer and tech hobbyist. Interested in game development.'),
('user_005', 'eve_cloud', 'DevOps engineer focused on AWS and Kubernetes. Infrastructure as code advocate.');

-- Insert sample community activity (for testing recent activity)
INSERT INTO community_activity (message_id, community_id, user_id, created_at) VALUES
-- Python SF - High activity
('msg_001', 'comm_py_sf_001', 'user_001', NOW() - INTERVAL '1 day'),
('msg_002', 'comm_py_sf_001', 'user_001', NOW() - INTERVAL '2 days'),
('msg_003', 'comm_py_sf_001', 'user_003', NOW() - INTERVAL '3 days'),
('msg_004', 'comm_py_sf_001', 'user_005', NOW() - INTERVAL '4 days'),

-- AI/ML SF - Medium activity
('msg_005', 'comm_ai_sf_001', 'user_001', NOW() - INTERVAL '1 day'),
('msg_006', 'comm_ai_sf_001', 'user_003', NOW() - INTERVAL '5 days'),

-- Gaming SF - Very high activity
('msg_007', 'comm_game_sf_001', 'user_004', NOW() - INTERVAL '1 hour'),
('msg_008', 'comm_game_sf_001', 'user_004', NOW() - INTERVAL '6 hours'),
('msg_009', 'comm_game_sf_001', 'user_002', NOW() - INTERVAL '1 day'),

-- Web NYC - Medium activity
('msg_010', 'comm_web_ny_001', 'user_002', NOW() - INTERVAL '2 days');

-- Insert some community memberships
INSERT INTO community_members (user_id, community_id, auto_joined) VALUES
('user_001', 'comm_py_sf_001', false),
('user_001', 'comm_ai_sf_001', false),
('user_002', 'comm_web_ny_001', false),
('user_002', 'comm_js_sf_001', false),
('user_003', 'comm_ds_sf_001', false),
('user_004', 'comm_game_sf_001', false),
('user_005', 'comm_cloud_sea_001', false);

-- Verify data
SELECT 'Communities created:' as info, COUNT(*) as count FROM communities
UNION ALL
SELECT 'Users created:', COUNT(*) FROM users
UNION ALL
SELECT 'Recent activities:', COUNT(*) FROM community_activity WHERE created_at >= NOW() - INTERVAL '7 days'
UNION ALL
SELECT 'Community memberships:', COUNT(*) FROM community_members;

-- Show sample data
SELECT 
    c.community_name,
    c.category,
    c.city,
    c.member_count,
    COUNT(ca.message_id) as recent_messages
FROM communities c
LEFT JOIN community_activity ca ON c.community_id = ca.community_id 
    AND ca.created_at >= NOW() - INTERVAL '7 days'
GROUP BY c.community_id, c.community_name, c.category, c.city, c.member_count
ORDER BY c.city, c.category
LIMIT 10;
