-- Function to get user quota information
CREATE OR REPLACE FUNCTION get_user_quota(user_uuid UUID)
RETURNS TABLE (
    tier TEXT,
    requests_today INTEGER,
    tokens_today INTEGER,
    subscription_status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        up.tier,
        COALESCE(usage_stats.requests_today, 0)::INTEGER as requests_today,
        COALESCE(usage_stats.tokens_today, 0)::INTEGER as tokens_today,
        up.subscription_status
    FROM user_profiles up
    LEFT JOIN (
        SELECT 
            user_id,
            COUNT(*) as requests_today,
            SUM(tokens_used) as tokens_today
        FROM api_usage 
        WHERE user_id = user_uuid 
        AND created_at >= CURRENT_DATE
        GROUP BY user_id
    ) usage_stats ON up.user_id = usage_stats.user_id
    WHERE up.user_id = user_uuid;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to create user profile on signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_profiles (user_id, email, tier, subscription_status)
    VALUES (NEW.id, NEW.email, 'free', 'inactive');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create profile on user signup
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Function to get training statistics
CREATE OR REPLACE FUNCTION get_training_stats()
RETURNS TABLE (
    total_documents INTEGER,
    training_ready INTEGER,
    avg_quality_score FLOAT,
    last_training TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::INTEGER as total_documents,
        COUNT(CASE WHEN is_training_ready THEN 1 END)::INTEGER as training_ready,
        AVG(quality_score)::FLOAT as avg_quality_score,
        (SELECT MAX(created_at) FROM training_jobs WHERE status = 'completed') as last_training
    FROM processed_content;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to clean old data
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS VOID AS $$
BEGIN
    -- Delete API usage older than 30 days
    DELETE FROM api_usage 
    WHERE created_at < NOW() - INTERVAL '30 days';
    
    -- Delete failed training jobs older than 7 days
    DELETE FROM training_jobs 
    WHERE status = 'failed' 
    AND created_at < NOW() - INTERVAL '7 days';
    
    -- Delete old scraped content (keep last 10000 per source)
    WITH ranked_content AS (
        SELECT id, ROW_NUMBER() OVER (PARTITION BY source ORDER BY scraped_at DESC) as rn
        FROM scraped_content
    )
    DELETE FROM scraped_content 
    WHERE id IN (
        SELECT id FROM ranked_content WHERE rn > 10000
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
