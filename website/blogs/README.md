# Adding a New Blog Post

## Steps

1. **Write your post** in Markdown — save it as `website/blogs/posts/<slug>.md`
   - The slug becomes part of the URL: `/blogs/post.html?slug=<slug>`
   - Use lowercase, hyphens for spaces (e.g., `my-new-post.md`)

2. **Add an entry** to `website/blogs/manifest.json`:

   ```json
   {
     "slug": "my-new-post",
     "title": "My New Post Title",
     "date": "2026-03-20",
     "excerpt": "A short description shown on the blog listing card."
   }
   ```

   - `slug` must match the `.md` filename (without extension)
   - `date` is displayed on the card and post page (YYYY-MM-DD format)
   - `excerpt` appears on the listing page — keep it to 1–2 sentences

3. **Deploy** — commit both files and push to `main`. The CI/CD pipeline automatically deploys the website to Azure Static Web Apps.

   ```bash
   git add website/blogs/posts/my-new-post.md website/blogs/manifest.json
   git commit -m "blog: add my-new-post"
   git push origin main
   ```

## Markdown Features Supported

The blog renderer uses [marked.js](https://marked.js.org/) — standard Markdown syntax:

- **Headings**: `# H1` through `#### H4`
- **Bold/Italic**: `**bold**`, `*italic*`
- **Links**: `[text](url)`
- **Images**: `![alt](assets/my-image.png)` — images are responsive and rounded
- **Lists**: `- item` or `1. item`
- **Blockquotes**: `> quote`
- **Code**: `` `inline` `` or fenced blocks with ` ``` `

## Adding Images

Place image files in `website/blogs/assets/` and reference them with relative paths in your Markdown:

```markdown
![Breathing diagram](assets/breathing-diagram.png)
```

Supported formats: `.png`, `.jpg`, `.webp`, `.svg`

Keep images reasonably sized — under 500KB per image is ideal since they're committed to the repo.

## Example

**File:** `website/blogs/posts/breathing-science.md`

```markdown
# The Science Behind Yogic Breathing

Pranayama isn't just tradition — it's neuroscience...
```

**Manifest entry:**

```json
{
  "slug": "breathing-science",
  "title": "The Science Behind Yogic Breathing",
  "date": "2026-03-25",
  "excerpt": "How ancient breathing practices align with modern neuroscience research."
}
```
