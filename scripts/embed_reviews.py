#!/usr/bin/env python3
import re
import base64
from pathlib import Path

base = Path(__file__).resolve().parent.parent
html_path = base / 'excalibur_mobile_landing_reviews-latest4.html'
reviews_dir = base / 'images' / 'reviews'

# Discover PNG files in the reviews directory (natural sort)
pngs = sorted([p for p in reviews_dir.iterdir() if p.suffix.lower() in ('.png', '.jpg', '.jpeg')], key=lambda p: p.name.lower())

# For each png, prefer an existing .b64 file named reviewN.b64, otherwise encode the png
b64_contents = []
for p in pngs:
    # attempt to find a matching .b64 by index if present (review1.b64 etc) or same-stem
    stem_index = None
    m = re.search(r'(\d+)', p.name)
    if m:
        stem_index = m.group(1)
    b64_candidate = None
    if stem_index:
        cand = reviews_dir / f'review{stem_index}.b64'
        if cand.exists():
            b64_candidate = cand.read_text().strip()
    if not b64_candidate:
        # try same-stem .b64
        cand2 = reviews_dir / (p.stem + '.b64')
        if cand2.exists():
            b64_candidate = cand2.read_text().strip()
    if b64_candidate:
        b64_contents.append(b64_candidate)
    else:
        # encode PNG/JPG to base64
        raw = p.read_bytes()
        b64_contents.append(base64.b64encode(raw).decode('ascii'))

# Build replacement HTML block that embeds base64 strings in a JS array and lazy-loads them into images
b64_js_array = ',\n'.join([f'"{b}"' for b in b64_contents])

# Create a carousel section: images placed in a flex track, lazy-loaded from embedded base64
template = """
<section id="reviews" class="py-16">
    <div class="max-w-6xl mx-auto px-4">
        <h2 class="text-2xl font-bold mb-4">Customer Reviews</h2>
        <div class="relative">
            <div class="overflow-hidden rounded-2xl">
                <div class="reviews-track flex transition-transform duration-500 will-change-transform">
                </div>
            </div>
            <div class="absolute left-2 top-1/2 -translate-y-1/2">
                <button class="reviews-prev bg-black/40 hover:bg-black/60 text-white px-3 py-2 rounded-full">‹</button>
            </div>
            <div class="absolute right-2 top-1/2 -translate-y-1/2">
                <button class="reviews-next bg-black/40 hover:bg-black/60 text-white px-3 py-2 rounded-full">›</button>
            </div>
            <div class="mt-3 flex justify-center gap-2 reviews-dots"></div>
        </div>
    </div>
    <script>
        const REVIEWS_B64 = [
            __B64_ARRAY__
        ];
        (function(){
            const track = document.querySelector('#reviews .reviews-track');
            if (!track) return;
            const total = REVIEWS_B64.length;
            // create slides
            REVIEWS_B64.forEach((b64,i) => {
                const slide = document.createElement('div');
                slide.className = 'w-full flex-shrink-0 p-3';
                slide.style.width = '100%';
                const wrap = document.createElement('div');
                wrap.className = 'rounded-2xl overflow-hidden border border-white/10 bg-white/5 flex items-center justify-center';
                const img = document.createElement('img');
                img.alt = `Customer photo ${i+1}`;
                img.className = 'w-full h-auto object-cover';
                img.loading = 'lazy';
                img.decoding = 'async';
                img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';
                if (b64) img.dataset.b64 = b64;
                wrap.appendChild(img);
                slide.appendChild(wrap);
                track.appendChild(slide);
            });

            // set track width
            const slides = track.children;
            track.style.width = `${slides.length * 100}%`;
            Array.from(slides).forEach(sl => sl.style.width = `${100 / slides.length}%`);

            // dots
            const dotsContainer = document.querySelector('#reviews .reviews-dots');
            for (let i=0;i<slides.length;i++){
                const d = document.createElement('button');
                d.className = 'w-2 h-2 rounded-full bg-white/40';
                d.dataset.index = i;
                d.addEventListener('click', ()=> goTo(i));
                dotsContainer.appendChild(d);
            }

            let idx = 0;
            const update = () => {
                track.style.transform = `translateX(-${idx * (100 / slides.length)}%)`;
                // update dots
                dotsContainer.querySelectorAll('button').forEach((b,bi)=> b.className = bi===idx ? 'w-2 h-2 rounded-full bg-yellow-400' : 'w-2 h-2 rounded-full bg-white/40');
            };
            const goTo = (i) => { idx = (i+slides.length)%slides.length; update(); };
            document.querySelector('#reviews .reviews-next').addEventListener('click', ()=> goTo(idx+1));
            document.querySelector('#reviews .reviews-prev').addEventListener('click', ()=> goTo(idx-1));

            // lazy-load visible images via IntersectionObserver
            const io = new IntersectionObserver((entries, obs)=>{
                entries.forEach(e=>{
                    if (!e.isIntersecting) return;
                    const img = e.target;
                    const b64 = img.dataset.b64;
                    if (b64) img.src = 'data:image/png;base64,'+b64;
                    obs.unobserve(img);
                });
            }, { root: document.querySelector('#reviews .overflow-hidden'), rootMargin: '200px' });
            track.querySelectorAll('img').forEach(i=> io.observe(i));

            // autoplay
            let autoplay = setInterval(()=> goTo(idx+1), 3500);
            // pause on hover
            track.addEventListener('mouseenter', ()=> clearInterval(autoplay));
            track.addEventListener('mouseleave', ()=> autoplay = setInterval(()=> goTo(idx+1), 3500));

            update();
        })();
    </script>
</section>
"""

replacement = template.replace('__B64_ARRAY__', b64_js_array)

# Read HTML and replace the first <!-- REVIEWS --> comment with the replacement
html = html_path.read_text()
if '<!-- REVIEWS -->' in html:
    new_html = html.replace('<!-- REVIEWS -->', replacement)
    html_path.write_text(new_html)
    print('embedded', sum(1 for b in b64_contents if b), 'images into HTML (placeholder)')
else:
    # replace existing <section id="reviews" ...>...</section>
    pattern = re.compile(r"<section\s+id=\"reviews\"[\s\S]*?</section>", re.I)
    if not pattern.search(html):
        print('No reviews section found; aborting')
    else:
        new_html = pattern.sub(replacement, html, count=1)
        html_path.write_text(new_html)
        print('embedded', sum(1 for b in b64_contents if b), 'images into HTML (replaced existing section)')
