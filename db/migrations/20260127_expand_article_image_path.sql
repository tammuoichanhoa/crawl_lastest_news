-- Expand image_path length to avoid truncating long CDN URLs.
ALTER TABLE article_images
    ALTER COLUMN image_path TYPE VARCHAR(2000);
