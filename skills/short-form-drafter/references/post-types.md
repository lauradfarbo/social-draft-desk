# Post types

Match on the calendar's Content type (column P). The client's names come from `workspace.json`:

| Generic type below | Matched by |
| --- | --- |
| Teaser | `calendar.teaser_regex` |
| Event live, Event recap | `calendar.event_live_regex` |
| Partner Win, Customer Proof | `calendar.proof_types` (values) |
| Team-owned rows | `calendar.team_owned_regex` |
| Any other type | The name below, or the client's name for it in `calendar.content_type_aliases` (`{"<client name>": "<generic type>"}`), when the config has that key |

If a content type matches none of these, draft it in the pattern of the nearest type below, say which in a flag, and add a flag starting "New type:" with a one-line playbook entry (draft when, what the post does, call to action, visual) for the approver to approve. The orchestrator lists new types in the brief.

## Every post

- Length: `writing.word_count` for the draft type (`post`, `founder`, `poll`; a video caption post uses `video` if set, else `post`). This replaces any word count in Spec (column Q). Everything else in Spec still applies.
- Opening sentence under `writing.opening_max_words` words, stating a tension or a concrete fact about the reader's work.
- One idea, one call to action.
- Hashtags at the end: between `writing.hashtags.min` and `max`, including every `required` tag, plus any `conditional` tag whose pattern the post matches.
- Links in the first comment when `writing.link_in_first_comment` is true, and the post says "Link in the first comment".

## Types

| Content type | Draft when | What the post does | Call to action | Visual |
| --- | --- | --- | --- | --- |
| Teaser (for a blog) | Always. Without the published link, write a base draft from the blog title and approved facts, with `[Blog N link]` in the first comment, and flag it "To finish:". When the link arrives, the orchestrator marks the row `refresh` and it is redrafted into a v2 tab | Hook plus one takeaway from the blog. Once published, read the blog; the teaser never claims more than the blog says | "Link in the first comment" plus a question | The blog header image if the blog row's Visual names one, else an assets file |
| Press release announcement | Always. Until the release is published and its link is in Notes on the distribution row, the link is a `[Press release link]` gap | A native LinkedIn post, not a copy of the release. Same facts only | Link to the release in the first comment | Assets file |
| Long-form source push (launch, push, event reminder with the source) | Always. If the landing page in the chapter map is not live yet, the link is a `[Landing page link]` gap | One problem the long-form source solves, drawn from one chapter; name what the reader gets. Vary the chapter across these posts (check Sources on earlier rows) | Landing page in the first comment | Assets file, or "Needed: <long-form source> cover graphic" |
| Industry POV | Always | The company's practitioner view on one problem the audience in the voice guide faces. Founder-style may use the `founder` word count | A question that invites experience | Usually none, or a photo of the team at work |
| Poll | Always | Short framing within the `poll` word count, then one question of 140 characters or fewer and 2 to 4 options of 30 characters or fewer | Vote and comment | None needed (LinkedIn renders the poll) |
| Event teaser | Always, unless the event is on hold | Event facts only from the facts sheet or person items: what, where, when, where to find the team. A missing stand number or time is a gap | Visit or join | Assets file |
| Event live, Event recap | Always. What happened comes from the facts, person items or Notes; until it does, write a base draft with `[what the team heard]` gaps | Recap: themes the team heard. Never invented conversations, visitor numbers or named companies | Teaser: visit. Recap: a question | Named assets photo; if none, `Needed: <real photo>` and the gap in What's missing |
| Event announcement, Event reminder | When the event is confirmed: its milestone has Confirmed `Yes`, its dependency fact is approved, or Notes say `CONFIRMED` with a date. While a hold stands, skip and write the reason in Notes | Event title, date and what attendees get (agenda items from the Milestones Notes in `person_items.json`, in the approver's words), and who it is for. Speakers, start time and registration link are gaps until the approver gives them. Apply `writing.custom_rules` even when an event title breaks one | Register, link in the first comment | Assets file; an AI image only for a generic scene |
| Gratitude | Always | Warm and specific to the year's real moments from the facts sheet. Thank partners, customers and the team without naming any organization unless it is signed off in the proof log | No hard call to action | Team photo from the assets folder |
| Year-in-review | Always | Light recap of approved milestones only. "In numbers" uses only approved figures; if too few exist, make it "in moments" and say so in Notes | No hard call to action | Assets photo or "Needed: year-in-review graphic" |
| Video (any) | Always | A shot list and a 60 to 90 second script (30 to 60 for a short product clip) with on-screen captions, plus the caption post | In the caption post | The video is the visual: "Needed: <the video>" unless it exists in the assets folder |
| Partner recruitment | Always | Invites the kind of partner the row names (resellers, integrators, consultancies) to talk to the company about working together. Only approved facts on how the company works with partners. Never name a partner unless it is signed off in the proof log; never promise margins, territories, pricing or launch dates | Comment or message the team; a link only if Notes give one | Assets file, or an AI image (no real people or logos) |
| Advisory board announcement | Always. With an Advisor item in `proof_item.json`, from it; with none, a base draft with the advisor's details as [bracketed] gaps (no flag, no swap) | Welcomes one advisor: name, role on the board, their organization and what they will help with, in the proof log's or the approver's words. Nothing about the advisor beyond that; no quote unless it is in the proof log word for word | Welcome them; invite the reader to follow along | `Needed: <advisor> headshot, with their permission` unless a photo of them is in the assets folder. Never an AI image of a real person |
| Partner Win, Customer Proof | Never by this skill | Proof intake drafts these. If asked, stop and say so | | |
| Team-owned rows (blog publish, newsletter, press release distribution) | Never | Skip without a note | | |

A row on an on-hold topic is not drafted while the hold stands: write "<topic> on hold: not drafted" as the Notes line. A hold is lifted by the dependency fact approved, a Milestones row of the dependency's `milestone_type` with Confirmed `Yes`, or `CONFIRMED` with a date in the row's Notes.

## Gaps

A base draft is a full post. Each missing item is [square-bracket text] where it belongs in the post or first comment: `[Blog 2 link]`, `[Speaker name and role]`, `[Photo of the team at the stand]`. Flags list each gap, "To finish:" first, then "To strengthen:". Never put a guessed name, figure or date inside the brackets as if it were true; describe what is needed.

## Hooks

Give one alternate hook with a different angle, not a reworded copy: for example, a tension hook and a fact hook.

## Visual line

Pick in this order and return one of these lines as `visual`:

1. **An assets file** that fits the post: `Use: <file name> (<visuals.asset_prefix>/<subfolder>)`. Only files in `assets.txt`. Never a file listed in `visuals_recent.txt`: it is already the visual of another row within the no-repeat window. Never a logo for a post that needs a photo. Never a meme file unless the post is light in tone and the meme fits.
2. **An AI image**, only when `visuals.ai_image_tool` is set and no unused file fits: `Needed: <AI image tool> image of <subject in up to 12 words>. Prompt in draft tab.` Return `image_prompt`, `image_alt_prompt` and `image_alt_subject` (the alternative's subject in up to 12 words, used if another post in the window already has a similar subject). Rules below. When `visuals.ai_image_tool` is null, write `Needed: <the photo or graphic, and what it shows>` instead and return no prompts.
3. **A real photo or video** when the content type matches `visuals.real_photo_only_regex` (typically event live and recap posts, Partner Win and Customer Proof). Never an AI image for these: `Needed: <the real photo, video or logo, and who provides it>`. Other posts may use an AI image, but it never stands in for a real person, team, event or site, and the post never presents it as one.
4. **Polls**: `None needed (LinkedIn renders the poll)`.

Separately from the Visual line, return `image_prompt` on every post when `visuals.ai_image_tool` is set, except types matching `visuals.real_photo_only_regex` and advisory board announcements: one ready-to-paste prompt the approver can use to make an image for this post, whatever the Visual line says. Same rules as below. The tab carries it twice (draft-doc-format.md): the editable line and the as-drafted copy. If `approver_prompt_edits.json` is in the bundle, write the prompt the way the approver edits prompts (subject, framing, detail added or cut).

Also return `visual_alternatives`: up to two more unused assets files that fit, as `Use:` lines (or an empty list). If another draft in the same run takes your file, the orchestrator switches to the first free alternative, then to your image prompt. So, when an AI image tool is set, give an image prompt whenever your visual is an assets file that other posts in the window might also want.

## Image prompts

The approver runs the prompt in the AI image tool and checks the image before use. Write each prompt as one paragraph of 60 to 120 words, in the client's spelling variety and units.

- **New subject.** The subject differs from every AI image subject in `visuals_recent.txt`: change the setting, the task and the shot. The alternative prompt is a different scene, not a reworded copy.
- **Setting from the audience.** Derive the scene from the audience the voice guide describes: the people the company sells to, at the work the post is about, in a setting that fits it. Photorealistic. People of varied ages and backgrounds. Natural light. Say the shot (close-up, eye level, over the shoulder). Any safety or work clothing is correct for the setting.
- **Product reference photo.** Only when `visuals.product_reference_photo` is set and the product appears in the image: start with "Using the attached reference photo of <product>," and add "Keep the product exactly as in the reference photo. Do not add screens, lights, logos or text to it." The approver attaches the photo when running the prompt. With no reference photo configured, keep the company's product out of the image.
- **Generic, not real.** An AI image shows a generic scene. It never depicts the company's team, a real event or a real site, and never claims to.
- **Never** show competitor products, brand logos, certification marks, a named customer or site, or a real person (no one in `company.people` and no public figure). Never show anything the facts sheet does not support, such as figures on a screen.
- **Abstract option.** Data, IT and process posts may use a clean diagram-style or abstract image in `visuals.brand_colors`.
- **Always end with** an aspect ratio from `visuals.aspect_ratios` and "No text, logos or watermarks in the image."

Example (fictional client: energy reporting software for facilities managers): "Create a photorealistic image of a facilities manager in a plant room at the start of the day, reading a printed meter log beside a row of electrical panels, with a tablet resting on a nearby cabinet. Calm, practical mood. Natural light from a high window, eye-level side view, shallow depth of field. Keep the tablet screen dark. 1.91:1 (1200 x 627). No text, logos or watermarks in the image."
