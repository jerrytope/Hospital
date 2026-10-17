"""Fill an empty site with original sample content so every template can be seen and tested.

    python manage.py seed_demo            # build the page tree, settings, menus and sample content
    python manage.py seed_demo --reset    # delete existing pages under the root first

Every number, name and bank detail created here is a SAMPLE. Replace it in the admin before launch.
"""
import io
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from wagtail.documents.models import Document
from wagtail.models import Page, Site
from wagtail.rich_text import RichText

from apps.about.models import FinancialReportsPage, HistoryPage, LeadershipPage, Person, Report, TimelineEntry
from apps.core import demo_photos as dp
from apps.core.models import FolderPage, NavigationSettings, OrganisationSettings
from apps.countries.models import Challenge, CountryImpactStat, CountryPage, ResponseSector, WhereWeWorkPage
from apps.emergencies.models import EmergencyFAQ, EmergencyIndexPage, EmergencyPage, MediaAlert, PastEmergency, SituationReport
from apps.giving.models import Appeal, BankAccount, DonationSettings, GiftItem, GiftsCatalogPage, GiftsFAQ
from apps.involvement.models import Event, Job, ListingPage, Tender
from apps.pages.models import ContactPage, DepartmentEmail, FAQItem, FAQPage, HomeImpactRow, HomePage, Office, StandardPage
from apps.programs.models import FocusArea, ProgramPage
from apps.resources.models import Resource
from apps.stories.models import StoriesIndexPage, StoryPage
from apps.taxonomy.models import Region, Topic

rng = random.Random(42)

def p(text):
    return "".join(f"<p>{para}</p>" for para in text.strip().split("\n\n"))


def r(text):
    """Rich text value for StreamField blocks."""
    return RichText(p(text))


class Command(BaseCommand):
    help = "Create demo pages, settings, menus and sample records."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing pages first")

    @transaction.atomic
    def handle(self, *args, **opts):
        root = Page.get_first_root_node()
        if opts["reset"]:
            for child in root.get_children():
                child.delete()
            for model in (Region, Topic, Resource, SituationReport, MediaAlert, PastEmergency, Person, Report, Office,
                          GiftItem, BankAccount, Appeal, Event, Tender, Job):
                model.objects.all().delete()
        elif HomePage.objects.exists():
            self.stdout.write(self.style.WARNING("A homepage already exists. Use --reset to rebuild the demo."))
            return

        # Remove Wagtail's default "Welcome" page so our homepage can take its place.
        Page.objects.filter(depth=2, content_type__app_label="wagtailcore", content_type__model="page").delete()
        self.make_taxonomy()
        home = self.make_home(root)
        self.home = home
        Site.objects.update_or_create(is_default_site=True, defaults={"root_page": home, "hostname": "localhost", "port": 80, "site_name": "Haven Medical Relief"})

        folders = {slug: self.add(home, FolderPage(title=slug.replace("-", " ").title(), slug=slug, show_in_menus=False))
                   for slug in ("program", "country", "emergency-response", "story", "updates", "video", "press-release", "supporter")}

        who = self.add(home, StandardPage(title="Who We Are", slug="who-we-are", show_in_menus=True, eyebrow="Who We Are",
                                          hero_intro="An independent humanitarian organisation delivering emergency medical care and lasting health services where they are needed most.",
                                          hero_image=self.photo(dp.PAGE_HEROES["who-we-are"])))
        what = self.add(home, StandardPage(title="What We Do", slug="what-we-do", show_in_menus=True, eyebrow="What We Do",
                                           hero_intro="We respond fast when disaster strikes, then stay to rebuild health systems so communities can stand on their own.",
                                           hero_image=self.photo(dp.PAGE_HEROES["what-we-do"])))
        www = self.add(home, WhereWeWorkPage(title="Where We Work", slug="where-we-work", show_in_menus=True, eyebrow="Where We Work",
                                             hero_intro="Our teams work in some of the hardest-to-reach places on earth, alongside local health workers.",
                                             hero_image=self.photo(dp.PAGE_HEROES["where-we-work"]),
                                             intro=p("Most of our staff are recruited from the communities we serve. Select a region to see where we work today.")))
        stories_index = self.add(home, StoriesIndexPage(title="Stories and News", slug="stories-and-news", show_in_menus=True,
                                                        eyebrow="Stories and News", hero_intro="News, updates and stories of hope from the field."))
        involved = self.add(home, StandardPage(title="Get Involved", slug="get-involved", show_in_menus=True, eyebrow="Get Involved",
                                               hero_heading="Be the reason a family gets care today",
                                               hero_intro="Monthly gifts let us respond the moment an emergency begins.", hero_image=self.photo(dp.PAGE_HEROES["get-involved"])))

        self.programs = self.make_programs(folders["program"])
        self.countries = self.make_countries(folders["country"])
        self.emergencies = self.make_emergencies(folders["emergency-response"])
        self.stories = self.make_stories(folders)
        self.link_tags()
        self.make_records()

        history, leadership, reports_page, faq, contact = self.make_who_we_are(who)
        emergencies_index, our_work = self.make_what_we_do(what, folders["program"])
        gifts_page, listings = self.make_get_involved(involved)
        legal = self.make_legal(home)
        self.add(stories_index, StandardPage(title="Media Center", slug="media-center", show_in_menus=True, eyebrow="Stories and News",
                                             hero_intro="Press releases, media contacts and spokespeople.",
                                             body=[("rich_text", r("For interviews and media enquiries please email <a href=\"mailto:media@example.org\">media@example.org</a>. Our spokespeople can speak about emergency response, maternal health, mental health and water and sanitation.")),
                                                   ("latest_stories", {"heading": "Press releases", "count": 6, "content_type": "press"})]))

        self.fill_home(home, our_work)
        self.fill_who_we_are(who, history)
        self.fill_get_involved(involved, gifts_page, listings)
        self.make_settings(home, who, what, www, stories_index, involved, history, leadership, reports_page, faq, contact,
                           emergencies_index, our_work, gifts_page, listings, legal)
        self.stdout.write(self.style.SUCCESS("Demo site ready. Everything is SAMPLE content: replace it in the admin."))

    # --- helpers ----------------------------------------------------------------------

    def add(self, parent, page):
        parent.add_child(instance=page)
        page.save_revision().publish()
        return page

    def republish(self, page):
        page.save_revision().publish()

    def photo(self, key):
        return dp.get_photo(key)

    def make_pdf(self, title):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(72, 760, title)
        c.setFont("Helvetica", 12)
        c.drawString(72, 730, "Sample document created by seed_demo. Replace it in the admin.")
        c.save()
        doc = Document(title=title)
        doc.file.save(f"{title.lower().replace(' ', '-')[:40]}.pdf", ContentFile(buf.getvalue()), save=False)
        doc.save()
        return doc

    # --- taxonomy ------------------------------------------------------------------------

    def make_taxonomy(self):
        self.regions = {}
        for i, name in enumerate(["Africa", "Asia", "Middle East", "Europe", "Americas"]):
            self.regions[name] = Region.objects.create(name=name, order=i)
        self.topics = {name: Topic.objects.create(name=name) for name in
                       ["Women and girls", "Refugees", "Climate", "Disease outbreaks", "Children", "Local health workers"]}

    # --- homepage -----------------------------------------------------------------------------

    def make_home(self, root):
        home = HomePage(
            title="Home", slug="home", hero_image=self.photo(dp.HOME_HERO),
            hero_heading="When disaster strikes, we are already on our way.",
            hero_appeal="Floods, conflict and outbreaks don't wait. Your gift today puts doctors, nurses and clean water where families need them most.",
            mission_text=p("We save lives and relieve suffering through emergency medical care, training and health services, and we stay to help communities build their own path to self-reliance."),
            donate_text="Gifts are tax-deductible where the law allows. 100% of emergency-designated gifts go to that emergency.",
            community_text="Field updates, emergency alerts and stories of hope, about twice a month.",
        )
        root.add_child(instance=home)
        home.save_revision().publish()
        return home

    def fill_home(self, home, our_work):
        rows = [
            ("Helping 4.2 million people last year", "Our teams delivered primary care, nutrition, mental health and water services across 26 countries.", our_work),
            ("1.1 million health consultations", "From mobile clinics in displacement camps to rebuilt district hospitals, we bring care to people cut off from it.", self.programs[1]),
            ("38,000 safe births", "Skilled birth attendants and emergency obstetric care help mothers and newborns survive the most dangerous moments.", self.programs[3]),
            ("620,000 people with clean water", "Wells, water trucking, latrines and hygiene kits stop the spread of cholera and other deadly diseases.", self.programs[5]),
            ("24,000 health workers trained", "Training local nurses, midwives and community health workers leaves skills behind long after an emergency ends.", None),
            ("Responding to disease outbreaks", "Rapid response teams isolate, treat and trace cases of cholera, measles and haemorrhagic fevers.", self.emergencies[1]),
            ("Mental health for survivors", "Counselling and community support help people recover from violence, loss and displacement.", self.programs[4]),
            ("Nutrition for the youngest", "We screen children for malnutrition and treat them before it becomes life-threatening.", self.programs[6]),
        ]
        for i, (headline, text, link) in enumerate(rows):
            HomeImpactRow.objects.create(page=home, sort_order=i, image=self.photo(dp.IMPACT_ROWS[i]), headline=f"{headline} (sample figure)", text=p(text), link_page=link)
        home.mission_link = StandardPage.objects.filter(slug="our-approach").first()
        self.republish(home)

    # --- programs -----------------------------------------------------------------------------

    def make_programs(self, folder):
        data = [
            ("Emergency Response", "ambulance", "We deploy medical teams within hours of a disaster and stay to help communities recover."),
            ("Health Services Support", "hospital", "We rebuild and run clinics and hospitals so people can get the care they need close to home."),
            ("Family and Community Health", "users", "Community health workers bring prevention and basic care to every household."),
            ("Women's and Children's Health", "baby", "Safe pregnancies, safe births and healthy childhoods, even in a crisis."),
            ("Mental Health", "brain", "Counselling and psychosocial support for people who have lived through violence, loss and displacement."),
            ("Water, Sanitation and Hygiene", "droplets", "Clean water, safe latrines and hygiene supplies that stop disease before it starts."),
            ("Nutrition and Food Security", "wheat", "Finding and treating malnutrition early, and helping families grow and buy enough food."),
        ]
        programs = []
        for i, (name, icon, short) in enumerate(data):
            page = ProgramPage(
                title=name, short_description=short, card_icon=icon, eyebrow="Our Work", hero_image=self.photo(dp.PROGRAMS[name]),
                hero_intro=short,
                intro=p(f"{short}\n\nOur {name.lower()} work is designed with local health authorities and delivered mostly by staff from the communities we serve. Everything on this page is sample content."),
                icon_stats=[("stat", {"icon": icon, "value": f"{rng.randint(10, 900)},000", "text": "people reached last year (sample)"}),
                            ("stat", {"icon": "map-pin", "value": f"{rng.randint(8, 24)}", "text": "countries with active programs (sample)"}),
                            ("stat", {"icon": "graduation-cap", "value": f"{rng.randint(1, 9)},{rng.randint(100, 999)}", "text": "local staff trained (sample)"})],
                achievements=[("item", t) for t in [
                    "Integrated services into national health systems in every country we work in.",
                    "Trained local teams who now lead the response in their own districts.",
                    "Reached remote communities through mobile teams and outreach workers.",
                    "Published guidance used by other humanitarian organisations.",
                ]],
                appeal_code=f"PROG-{name.split()[0].upper()[:8]}",
            )
            folder.add_child(instance=page)
            for j, area in enumerate(["Prevention", "Treatment", "Training", "Community"]):
                FocusArea.objects.create(page=page, sort_order=j, title=area,
                                         overview=p(f"Our {area.lower()} work in {name.lower()} focuses on reaching people early and building local capacity. (Sample text.)"),
                                         key_stats=[("stat", {"icon": "activity", "value": f"{rng.randint(5, 95)}%", "text": "sample indicator"}),
                                                    ("stat", {"icon": "users", "value": f"{rng.randint(2, 60)},000", "text": "people supported (sample)"})])
            page.save_revision().publish()
            programs.append(page)
        return programs

    # --- countries -----------------------------------------------------------------------------

    def make_countries(self, folder):
        current = [
            ("Nigeria", "Africa", 9.08, 8.68, 2013), ("Democratic Republic of the Congo", "Africa", -4.04, 21.76, 1999),
            ("South Sudan", "Africa", 6.88, 31.31, 1994), ("Sudan", "Africa", 12.86, 30.22, 2004), ("Somalia", "Africa", 5.15, 46.20, 1991),
            ("Ethiopia", "Africa", 9.15, 40.49, 2003), ("Chad", "Africa", 15.45, 18.73, 2004), ("Mali", "Africa", 17.57, -4.00, 2013),
            ("Cameroon", "Africa", 7.37, 12.35, 2015), ("Kenya", "Africa", -0.02, 37.91, 2000), ("Libya", "Africa", 26.34, 17.23, 2011),
            ("Afghanistan", "Asia", 33.94, 67.71, 2001), ("Pakistan", "Asia", 30.38, 69.35, 2005), ("Bangladesh", "Asia", 23.68, 90.36, 2017),
            ("Nepal", "Asia", 28.39, 84.12, 2015), ("Myanmar", "Asia", 21.91, 95.96, 2008), ("Philippines", "Asia", 12.88, 121.77, 2013),
            ("Syria", "Middle East", 34.80, 38.99, 2008), ("Yemen", "Middle East", 15.55, 48.52, 2012), ("Iraq", "Middle East", 33.22, 43.68, 2003),
            ("Jordan", "Middle East", 30.59, 36.24, 2007), ("Lebanon", "Middle East", 33.85, 35.86, 2006),
            ("Ukraine", "Europe", 48.38, 31.17, 2014), ("Bosnia and Herzegovina", "Europe", 43.92, 17.68, 1994),
            ("Haiti", "Americas", 18.97, -72.29, 2010), ("Venezuela", "Americas", 6.42, -66.59, 2019), ("Colombia", "Americas", 4.57, -74.30, 2019),
            ("Mexico", "Americas", 23.63, -102.55, 2018),
        ]
        past = [("Sierra Leone", "Africa", 8.46, -11.78, True), ("Liberia", "Africa", 6.43, -9.43, False), ("Rwanda", "Africa", -1.94, 29.87, False),
                ("Angola", "Africa", -11.20, 17.87, False), ("Indonesia", "Asia", -0.79, 113.92, True), ("Sri Lanka", "Asia", 7.87, 80.77, False),
                ("Japan", "Asia", 36.20, 138.25, False), ("Iran", "Middle East", 32.43, 53.69, False), ("Kosovo", "Europe", 42.60, 20.90, False),
                ("North Macedonia", "Europe", 41.61, 21.75, False), ("Honduras", "Americas", 15.20, -86.24, False), ("Peru", "Americas", -9.19, -75.02, False)]
        countries = []
        for i, (name, region, lat, lng, since) in enumerate(current):
            page = CountryPage(
                title=name, region=self.regions[region], status="current", work_started=since,
                latitude=Decimal(str(lat)), longitude=Decimal(str(lng)), eyebrow="Where We Work",
                hero_image=self.photo(dp.country_key(region, sum(1 for c in current[:i] if c[1] == region))),
                hero_intro=f"Delivering health care and emergency relief in {name} since {since}.",
                intro=p(f"We began working in {name} in {since}. Today our teams provide primary health care, nutrition, mental health and water and sanitation services, working closely with the Ministry of Health and local partners.\n\nThis is sample text: replace it with the real country context."),
                response_intro=p("Our response combines emergency services with long-term support for the local health system. (Sample text.)"),
                impact_year=timezone.localdate().year - 1, appeal_code=f"CTRY-{name.split()[0].upper()[:8]}",
            )
            if name == "Nigeria":
                page.population, page.life_expectancy, page.infant_mortality = "Sample: 220 million", "Sample: 54 years", "Sample: 70 per 1,000"
                page.award_heading = "Partner of the Year (sample award)"
                page.award_text = p("A placeholder for an award or supporter profile feature.")
            folder.add_child(instance=page)
            for j, (icon, title, text) in enumerate([("swords", "Armed conflict", "Violence has forced families from their homes."),
                                                     ("wheat", "Food insecurity", "Many families can't count on their next meal."),
                                                     ("tent", "Displacement", "Millions live in camps or host communities.")]):
                Challenge.objects.create(page=page, sort_order=j, icon=icon, title=title, text=text)
            for j, (icon, title) in enumerate([("apple", "Nutrition and Food Security"), ("stethoscope", "Health care"),
                                               ("droplets", "Water, Sanitation and Hygiene"), ("shield-alert", "Protection")]):
                ResponseSector.objects.create(page=page, sort_order=j, icon=icon, title=title,
                                              text=p(f"Sample description of our {title.lower()} work in {name}."))
            for j, (v, label) in enumerate([("1.2 million", "people reached"), ("350,000", "consultations"), ("12,000", "children treated for malnutrition"), ("9 million", "litres of clean water")]):
                CountryImpactStat.objects.create(page=page, sort_order=j, value=v, label=f"{label} (sample)")
            page.programs.set(rng.sample(self.programs, 3))
            page.save_revision().publish()
            countries.append(page)
        for name, region, lat, lng, has_page in past:
            page = CountryPage(title=name, region=self.regions[region], status="past", has_detail_page=has_page,
                               latitude=Decimal(str(lat)), longitude=Decimal(str(lng)), eyebrow="Where We Work",
                               intro=p(f"We worked in {name} in the past. (Sample text.)"))
            self.add(folder, page)
        return countries

    def country(self, name):
        return next(c for c in self.countries if c.title == name)

    # --- emergencies ----------------------------------------------------------------------

    def make_emergencies(self, folder):
        y = timezone.localdate().year
        data = [
            ("Flood Response in the Lake Chad Basin", "active", True, y, None, ["Nigeria", "Chad", "Cameroon"], "FLOODS-LCB",
             "Record rains have flooded homes, farms and clinics across the Lake Chad Basin."),
            ("Cholera Outbreak Response", "active", True, y, None, ["Democratic Republic of the Congo", "Somalia"], "CHOLERA",
             "Our teams are treating patients and restoring clean water to stop the spread."),
            ("Earthquake Relief", "active", True, y, None, ["Nepal"], "QUAKE",
             "Mobile medical teams are reaching villages cut off by landslides."),
            ("Sahel Hunger Crisis", "ongoing", False, y - 3, None, ["Mali", "Chad"], "SAHEL", "Drought and conflict have left millions short of food."),
            ("Displacement Crisis in Sudan", "ongoing", False, y - 2, None, ["Sudan", "South Sudan", "Chad"], "SUDAN", "Families fleeing violence need health care and protection."),
            ("War in Ukraine", "ongoing", False, y - 4, None, ["Ukraine"], "UKRAINE", "Health care and mental health support for people affected by the war."),
            ("Syria Crisis", "ongoing", False, 2011, None, ["Syria", "Jordan", "Lebanon"], "SYRIA", "More than a decade of crisis has devastated the health system."),
        ]
        emergencies = []
        for i, (title, status, featured, ys, ye, countries, code, summary) in enumerate(data):
            page = EmergencyPage(
                title=title, status=status, featured=featured, year_start=ys, year_end=ye, card_summary=summary,
                eyebrow="Emergency Response", hero_image=self.photo(dp.EMERGENCIES[title]), hero_intro=summary, appeal_code=code,
                summary=p(f"{summary}\n\nThis is a sample situation summary. Describe what has happened, who is affected and what our teams are doing right now."),
                donate_text="Your gift goes directly to this emergency response.",
                key_facts=[("fact", {"icon": "users", "value": "1.4 million", "text": "people affected (sample)"}),
                           ("fact", {"icon": "tent", "value": "300,000", "text": "people displaced (sample)"}),
                           ("fact", {"icon": "ambulance", "value": "24", "text": "mobile medical teams deployed (sample)"})],
                responses=[("country", {"heading": c, "intro": r(f"Our response in {c}."), "sections": [
                    {"heading": "Health care", "text": r("Mobile clinics and support to health facilities. (Sample.)")},
                    {"heading": "Water and sanitation", "text": r("Water trucking, latrines and hygiene kits. (Sample.)")}]}) for c in countries],
                history=p("A short history of the crisis and of our work in the region. (Sample text.)"),
                expertise=p("Why our teams are equipped to respond: decades of experience in outbreak response and emergency health. (Sample text.)"),
            )
            folder.add_child(instance=page)
            for j, (q, a) in enumerate([("How is my gift used?", "Gifts made on this page go to this emergency response."),
                                        ("Are you already on the ground?", "Yes. Our local teams were working in the area before the emergency began.")]):
                EmergencyFAQ.objects.create(page=page, sort_order=j, question=q, answer=p(a))
            page.countries.set([self.country(c) for c in countries])
            page.programs.set([self.programs[0], self.programs[5]])
            page.save_revision().publish()
            Appeal.objects.update_or_create(code=code, defaults={"name": title, "emergency": page})
            emergencies.append(page)
        return emergencies

    # --- stories -----------------------------------------------------------------------------

    def make_stories(self, folders):
        titles = [
            ("story", "A Midwife's Night in the Flood Zone", "When the water rose, Hauwa kept the maternity ward open."),
            ("story", "Clean Water Returns to Kalemie", "A restored water network is keeping cholera away from thousands of homes."),
            ("story", "Learning to Heal: Counselling After Conflict", "Community counsellors are helping survivors talk about what they lived through."),
            ("story", "The Mobile Clinic That Reached the Mountains", "Our team walked six hours to reach villages cut off by the earthquake."),
            ("story", "Treating Malnutrition Before It's Too Late", "Mothers are learning to screen their own children for malnutrition."),
            ("story", "Nurses Who Became Trainers", "Five years after their own training, these nurses now train others."),
            ("update", "Situation Update: Lake Chad Basin Floods", "The latest on our flood response, updated weekly."),
            ("update", "Cholera Response: Week Six", "Cases are falling where water and treatment centres are in place."),
            ("video", "Video: A Day with Our Mobile Medical Team", "Follow a mobile team from dawn to dusk."),
            ("press", "Press Release: Emergency Teams Deploy to Flood-Affected Areas", "Medical teams and supplies are on their way."),
            ("press", "Press Release: New Maternal Health Program Launched", "A new program will support safe births in 40 health facilities."),
            ("supporter", "Supporter Profile: Running 100 km for Clean Water", "Why one supporter turned a running challenge into a fundraiser."),
            ("story", "A School Turned Health Post", "When the clinic was destroyed, the community found another way."),
            ("story", "Snapshots From the Field", "A month of our work, in pictures."),
        ]
        folder_for = {"story": "story", "update": "updates", "video": "video", "press": "press-release", "supporter": "supporter"}
        stories = []
        today = timezone.localdate()
        for i, (stype, title, dek) in enumerate(titles):
            body = [
                ("rich_text", r(f"{dek}\n\nThis is a sample story written for the demo site. It shows how a long-form story looks, with paragraphs, a pull quote and an image with a caption.\n\nReplace it with real reporting from the field, gathered with the informed consent of everyone featured.")),
                ("quote", {"quote": "We stayed because the people here needed us, and because they would have done the same for us.", "name": "Sample name", "role": "Community health worker"}),
                ("image", {"image": self.photo(dp.STORIES[title][1]), "caption": "Sample caption describing the photo.", "full_width": False}),
                ("rich_text", r("Every gift helps teams like this one reach more families. Thank you for standing with them.")),
            ]
            page = StoryPage(title=title, story_type=stype, dek=dek, date=today - timedelta(days=i * 6 + 1), author="Communications Team",
                             location=rng.choice(["Maiduguri, Nigeria", "Kalemie, DRC", "Gorkha, Nepal", "Mogadishu, Somalia", "Kharkiv, Ukraine"]),
                             photo_credit="Unsplash (sample photo)", hero_image=self.photo(dp.STORIES[title][0]), body=body,
                             featured=(i == 0), highlighted=(i in (1, 2, 3)),
                             video_url="https://www.youtube.com/watch?v=aqz-KE-bpKQ" if stype == "video" else "")
            folders[folder_for[stype]].add_child(instance=page)
            page.save_revision().publish()
            stories.append(page)
        return stories

    def link_tags(self):
        for i, s in enumerate(self.stories):
            s.programs.set(rng.sample(self.programs, 2))
            s.countries.set(rng.sample(self.countries[:12], 2))
            s.emergencies.set([self.emergencies[i % 3]])
            s.topics.set(rng.sample(list(self.topics.values()), 2))
            s.save_revision().publish()
        for e in self.emergencies[:3]:
            e.featured_stories.set(self.stories[:2])
            e.save_revision().publish()
        self.programs[4].featured_story = self.stories[2]
        self.republish(self.programs[4])
        nigeria = self.country("Nigeria")
        nigeria.featured_emergency = self.emergencies[0]
        self.republish(nigeria)

    # --- other records ------------------------------------------------------------------------

    def make_records(self):
        today = timezone.localdate()
        doc = self.make_pdf("Sample capability statement")
        for i in range(6):
            r = Resource.objects.create(title=f"Sample resource {i + 1}: {rng.choice(['Capability statement', 'Needs assessment', 'Field toolkit', 'Webinar recording'])}",
                                        date=today - timedelta(days=30 * i), kind=rng.choice(["capability", "assessment", "toolkit", "webinar"]),
                                        document=doc if i % 2 == 0 else None, url="" if i % 2 == 0 else "https://example.org/resource")
            r.programs.set(self.programs[:4])
            r.countries.set(self.countries[:5])
            r.emergencies.set(self.emergencies[:3])
        sitrep = self.make_pdf("Sample situation report")
        for e in self.emergencies[:3]:
            for n in range(1, 4):
                SituationReport.objects.create(title=f"{e.title}: Situation Report", number=n, date=today - timedelta(days=7 * (4 - n)),
                                               document=sitrep, emergency=e, country=e.countries.first())
            for n, outlet in enumerate(["The Daily Sample", "World Radio Example", "Global News Placeholder"]):
                MediaAlert.objects.create(date=today - timedelta(days=n * 3), outlet=outlet, headline=f"Our teams respond to {e.title.lower()} (sample)",
                                          url="https://example.org/news", emergency=e)
        past = [("Nigeria", "Meningitis outbreak", "2017"), ("Philippines", "Typhoon", "2013"), ("Haiti", "Earthquake", "2010"),
                ("Pakistan", "Floods", "2022"), ("Sierra Leone", "Ebola outbreak", "2014"), ("Indonesia", "Tsunami", "2004"),
                ("Nepal", "Earthquake", "2015"), ("Mozambique", "Cyclone", "2019"), ("Lebanon", "Port explosion", "2020"),
                ("Turkey", "Earthquake", "2023"), ("Libya", "Floods", "2023"), ("Morocco", "Earthquake", "2023"),
                ("Bangladesh", "Refugee influx", "2017"), ("Yemen", "Cholera outbreak", "2017"), ("Somalia", "Drought", "2011"),
                ("Japan", "Earthquake and tsunami", "2011"), ("Iraq", "Displacement", "2014"), ("Liberia", "Ebola outbreak", "2014")]
        for i, (c, n, y) in enumerate(past):
            PastEmergency.objects.create(country=c, name=n, year=y, order=i,
                                         details=p(f"Sample description of our {n.lower()} response in {c}, {y}.") if i % 3 else "",
                                         page=self.emergencies[0] if i == 0 else None)
        # Leadership (fictional placeholder names)
        Person.objects.create(name="Dr. Amara Placeholder", title="Co-founder", group="featured", order=0, photo=self.photo(dp.PEOPLE["Dr. Amara Placeholder"]),
                              bio=p("Sample biography. Replace with the founder's real biography."))
        Person.objects.create(name="Tunde Example", title="President and CEO", group="featured", order=1, photo=self.photo(dp.PEOPLE["Tunde Example"]),
                              bio=p("Sample biography. Replace with the chief executive's real biography."))
        for i in range(8):
            Person.objects.create(name=f"Board Member {i + 1}", title="Director" if i else "Chair", group="board", order=i)
        for i in range(12):
            Person.objects.create(name=f"Council Member {i + 1}", group="council", company="Sample Company Ltd", city=rng.choice(["Lagos", "Abuja", "London", "New York"]), order=i)
        for i in range(5):
            Person.objects.create(name=f"Ambassador {i + 1}", title="Global Ambassador, actor and advocate (sample)", group="ambassador", order=i)
        for i, t in enumerate(["Chief Operating Officer", "Chief Financial Officer", "Director of Programs", "Director of Communications"]):
            Person.objects.create(name=f"Executive {i + 1}", title=t, group="executive", order=i)
        for i in range(3):
            Person.objects.create(name=f"UK Trustee {i + 1}", group="affiliate", affiliate_name="UK Affiliate Board", order=i)
        # Reports
        year = today.year
        for i in range(4):
            Report.objects.create(report_type="annual", year=year - 1 - i, title=f"Annual Report {year - 1 - i}",
                                  summary="Sample summary of the year's work and finances.", cover=self.photo(dp.REPORT_COVERS[i]), document=self.make_pdf(f"Annual Report {year - 1 - i}"))
            Report.objects.create(report_type="impact", year=year - 1 - i, title=f"Impact Report {year - 1 - i}", document=doc)
            Report.objects.create(report_type="audit", year=year - 1 - i, title=f"Audited statements {year - 1 - i}", document=doc)
            Report.objects.create(report_type="tax", year=year - 1 - i, title=f"Tax return {year - 1 - i}", document=doc)
        # Offices
        Office.objects.create(name="Headquarters (sample)", address="12 Sample Street\nVictoria Island, Lagos\nNigeria", phone="+234 1 000 0000",
                              emails="General: info@example.org\nDonations: donate@example.org", order=0)
        Office.objects.create(name="Abuja Office (sample)", address="4 Example Crescent\nWuse II, Abuja", phone="+234 9 000 0000", order=1)
        Office.objects.create(name="UK Affiliate (sample)", address="1 Placeholder Road\nLondon", phone="+44 20 0000 0000", emails="uk@example.org", order=2)
        Office.objects.create(name="US Affiliate (sample)", address="100 Example Avenue\nWashington, DC", phone="+1 202 000 0000", emails="us@example.org", order=3)
        # Gifts catalog
        gifts = [("Emergency medical kit", 25000, 25), ("Clean water for a family", 15000, 15), ("Safe birth kit", 10000, 10),
                 ("Nutrition treatment for a child", 40000, 40), ("Train a community health worker", 75000, 75), ("Hygiene kits for 5 families", 20000, 20),
                 ("Vaccines for 20 children", 30000, 30), ("Counselling sessions", 35000, 35), ("Mosquito nets for a village", 50000, 50),
                 ("Solar lamp for a clinic", 45000, 45), ("Wheelchair", 90000, 90), ("Stock a pharmacy", 150000, 150)]
        for i, (t, ngn, usd) in enumerate(gifts):
            GiftItem.objects.create(title=t, price_ngn=Decimal(ngn), price_usd=Decimal(usd), order=i, image=self.photo(dp.GIFTS[t]),
                                    blurb="A symbolic gift: your money supports our work where it's needed most. (Sample text.)")
        # Bank accounts (SAMPLE: replace before launch)
        BankAccount.objects.create(bank_name="Sample Bank Plc", account_name="Haven Medical Relief", account_number="0000000000", currency="NGN",
                                   instructions="SAMPLE ACCOUNT: replace with your real account in Admin > Giving > Bank accounts.", order=0)
        BankAccount.objects.create(bank_name="Example International Bank", account_name="Haven Medical Relief", account_number="000000000000", currency="USD",
                                   swift_code="SAMPLEXX", instructions="SAMPLE ACCOUNT: for international transfers. Replace before launch.", order=1)
        for code, name in [("HOME-HERO", "Homepage hero"), ("HOME-BAND", "Homepage donate band"), ("HEADER", "Header button"),
                           ("FOOTER", "Footer"), ("STORY", "Story pages"), ("GIFTS", "Gifts catalog"), ("BANK-TRANSFER", "Bank transfers"),
                           ("MOBILE-STICKY", "Mobile sticky button"), ("FUNDRAISER", "Supporter fundraisers")]:
            Appeal.objects.get_or_create(code=code, defaults={"name": name})
        now = timezone.now()
        Event.objects.create(title="Annual Gala Dinner (sample)", start=now + timedelta(days=45), place="Lagos", description=p("Join us for an evening of stories from the field."), ticket_url="https://example.org/tickets")
        Event.objects.create(title="Charity Fun Run (sample)", start=now + timedelta(days=80), place="Abuja", description=p("5 km and 10 km routes for all abilities."))
        t = Tender.objects.create(title="Supply of medical consumables (sample)", reference="T-0001", country="Nigeria", deadline=now + timedelta(days=21), description=p("Sample tender description."))
        from apps.involvement.models import TenderDocument
        TenderDocument.objects.create(tender=t, title="Terms of reference", document=doc)
        Job.objects.create(title="Field Medical Coordinator (sample)", location="Maiduguri, Nigeria", job_type="full_time", deadline=today + timedelta(days=30),
                           summary="Lead our medical teams in the northeast.", description=p("Sample job description."), apply_email="jobs@example.org")
        Job.objects.create(title="Mental Health Officer (sample)", location="Juba, South Sudan", job_type="contract", deadline=today + timedelta(days=20),
                           summary="Run community mental health services.", apply_url="https://example.org/apply")

    # --- section pages ----------------------------------------------------------------------

    def make_who_we_are(self, who):
        mission = self.add(who, StandardPage(title="Mission", slug="mission", show_in_menus=True, eyebrow="Who We Are", hero_image=self.photo(dp.PAGE_HEROES["mission"]),
                                             hero_intro="Why we exist, and what we will always stand for.",
                                             body=[("rich_text", r("Our mission is to improve the quality of life through health interventions and related activities that build local capacity in underserved communities worldwide. (Sample text.)")),
                                                   ("icon_points", {"heading": "How we work", "items": [
                                                       {"icon": "ambulance", "title": "First on the scene", "text": "We respond within hours."},
                                                       {"icon": "users", "title": "Locally led", "text": "Most of our staff come from the communities we serve."},
                                                       {"icon": "graduation-cap", "title": "Skills that stay", "text": "Training leaves capacity behind."}]})]))
        values = self.add(who, StandardPage(title="Our Values", slug="our-values", show_in_menus=True, eyebrow="Who We Are",
                                            body=[("icon_points", {"heading": "What guides us", "items": [
                                                {"icon": "heart", "title": "Humanity", "text": "Every person deserves care and dignity."},
                                                {"icon": "scale", "title": "Impartiality", "text": "We help based on need alone."},
                                                {"icon": "shield-alert", "title": "Accountability", "text": "We answer to the people we serve and to our donors."}]})]))
        history = self.add(who, HistoryPage(title="Our History", slug="our-history", show_in_menus=True, eyebrow="Who We Are", hero_image=self.photo(dp.PAGE_HEROES["our-history"]),
                                            hero_intro="From a small volunteer team to a global humanitarian organisation.",
                                            intro=p("Sample timeline. Add one entry for each milestone in the admin.")))
        for i, (year, title) in enumerate([("1990", "Founded by volunteer doctors"), ("1994", "First refugee health program"),
                                            ("1999", "Emergency response in Central Africa"), ("2004", "Tsunami response"),
                                            ("2010", "Earthquake relief in the Caribbean"), ("2013", "Programs open in Nigeria"),
                                            ("2014", "Ebola treatment centres"), ("2015", "Earthquake response in Nepal"),
                                            ("2017", "Cholera response at scale"), ("2020", "Pandemic response in 20 countries"),
                                            ("2023", "Earthquake response across two countries"), (str(timezone.localdate().year), "Working in 28 countries")]):
            TimelineEntry.objects.create(page=history, sort_order=i, year=year, title=title, text=p("Sample description of this milestone."),
                                         photo=self.photo(dp.TIMELINE[i]), featured=i in (0, 6, 11))
        history.end_links = [("cards", {"cards": [
            {"image": self.photo(dp.CARDS["Where We Work"]), "label": "Explore", "title": "Where We Work", "text": "", "link": {"label": "See the map", "page": None, "url": "/where-we-work/"}},
            {"image": self.photo(dp.CARDS["What We Do"]), "label": "Explore", "title": "What We Do", "text": "", "link": {"label": "Our programs", "page": None, "url": "/what-we-do/"}}]})]
        self.republish(history)
        leadership = self.add(who, LeadershipPage(title="Leadership", slug="leadership", show_in_menus=True, eyebrow="Who We Are",
                                                  intro=p("We are part of a global alliance of independent affiliate organisations that share one mission. (Sample text.)")))
        reports_page = self.add(who, FinancialReportsPage(title="Accountability and Financial Reports", slug="financial-reports", show_in_menus=True,
                                                          eyebrow="Who We Are", hero_intro="How we use every gift, and how we're held to account.",
                                                          efficiency_value="90%", efficiency_text="of our spending goes directly to programs (sample figure)",
                                                          ratings_text=p("Sample text about charity ratings, audits and memberships of humanitarian standards bodies.")))
        self.add(who, StandardPage(title="Ethics and Compliance", slug="ethics", show_in_menus=True, eyebrow="Who We Are",
                                   body=[("rich_text", r("Our code of conduct, safeguarding policy and how to report a concern. (Sample text.)"))]))
        faq = self.add(who, FAQPage(title="Frequently Asked Questions", slug="frequently-asked-questions", show_in_menus=True, eyebrow="Who We Are",
                                    side_text=p("Can't find your answer? Get in touch.")))
        questions = ["Who are you?", "Where do you work?", "How are you different from other organisations?", "How are you funded?",
                     "How much of my gift goes to programs?", "Do you run programs other than health?", "How can I work for you?",
                     "How do you keep your staff safe?", "How do you make sure your work is ethical?", "Do you get consent for photos?",
                     "I'm a journalist. Who do I contact?", "How can I help?"]
        for i, q in enumerate(questions):
            FAQItem.objects.create(page=faq, sort_order=i, question=q, answer=p("Sample answer. Write your organisation's own answer here."))
        self.republish(faq)
        contact = self.add(who, ContactPage(title="Contact Us", slug="contact", show_in_menus=True, eyebrow="Who We Are",
                                            intro=p("We don't use a contact form. Please call or email the office or department that can help you.")))
        for i, (label, email) in enumerate([("Donations", "donate@example.org"), ("Media", "media@example.org"), ("Events", "events@example.org"),
                                            ("Jobs", "jobs@example.org"), ("International recruitment", "recruit@example.org"),
                                            ("Webmaster", "web@example.org"), ("General enquiries", "info@example.org")]):
            DepartmentEmail.objects.create(page=contact, sort_order=i, label=label, email=email)
        self.republish(contact)
        self.mission, self.values = mission, values
        return history, leadership, reports_page, faq, contact

    def fill_who_we_are(self, who, history):
        who.body = [
            ("rich_text", r("We are an independent, non-profit humanitarian organisation. Since our founding, we have delivered emergency medical care to millions of people affected by conflict, disease and disaster, and trained thousands of local health workers. (Sample text.)")),
            ("timeline_teaser", {"heading": "Our Rich History", "history_page": history, "count": 3}),
            ("quote", {"quote": "The courage of the health workers I met in the field changed how I see the world.", "name": "Sample Ambassador", "role": "Global Ambassador"}),
        ]
        self.republish(who)

    def make_what_we_do(self, what, program_folder):
        approach = self.add(what, StandardPage(title="Our Approach", slug="our-approach", show_in_menus=True, eyebrow="What We Do", hero_image=self.photo(dp.PAGE_HEROES["our-approach"]),
                                               hero_intro="Relief to self-reliance.",
                                               body=[("rich_text", r("We respond to emergencies, then stay to rebuild. Training local health workers means care continues long after the crisis. (Sample text.)"))]))
        our_work = self.add(what, StandardPage(title="Our Work", slug="our-work", show_in_menus=True, eyebrow="What We Do",
                                               hero_intro="Seven program areas, one goal: health care for everyone, everywhere.",
                                               body=[("child_pages", {"heading": "Our programs", "parent": program_folder})]))
        index = self.add(what, EmergencyIndexPage(title="Emergencies", slug="emergencies", show_in_menus=True, eyebrow="What We Do", hero_image=self.photo(dp.PAGE_HEROES["emergencies"]),
                                                  hero_intro="Where our emergency teams are responding right now.",
                                                  intro=p("When disaster strikes, our teams are often first on the scene. (Sample text.)")))
        for title in ("Training", "Research", "Partnerships"):
            self.add(what, StandardPage(title=title, slug=title.lower(), show_in_menus=True, eyebrow="What We Do",
                                        body=[("rich_text", r(f"How {title.lower()} strengthens our work. (Sample text.)"))]))
        what.body = [
            ("rich_text", r("We deliver emergency relief and long-term health services, built around seven program areas. (Sample text.)")),
            ("child_pages", {"heading": "Our programs", "parent": program_folder}),
            ("active_emergencies", {"heading": "Current emergencies", "count": 3}),
        ]
        self.republish(what)
        return index, our_work

    def make_get_involved(self, involved):
        gifts = self.add(involved, GiftsCatalogPage(title="Gifts of Hope", slug="gifts", show_in_menus=True, eyebrow="Get Involved", hero_image=self.photo(dp.PAGE_HEROES["gifts"]),
                                                    hero_intro="Meaningful gifts for the people you love, and for families in crisis.",
                                                    intro=p("Choose a symbolic gift, then send an e-card to let someone know a gift was made in their name.")))
        for i, (q, a) in enumerate([("Is checkout secure?", "Yes. Card payments are handled by Paystack or Stripe; we never see your card details."),
                                    ("Will I get a receipt?", "Yes, a receipt is emailed as soon as your payment is confirmed."),
                                    ("When does my e-card arrive?", "Within 2 hours of the send time you choose."),
                                    ("Can I send an e-card anonymously?", "No. E-cards always show your name, but never the amount."),
                                    ("Can I choose the country my gift goes to?", "No. Gifts support our work where it's needed most.")]):
            GiftsFAQ.objects.create(page=gifts, sort_order=i, question=q, answer=p(a))
        self.republish(gifts)
        other = self.add(involved, StandardPage(title="Other Ways to Give", slug="other-ways-to-give", show_in_menus=True, eyebrow="Get Involved",
                                                body=[("child_pages", {"heading": "More ways to support our work"})]))
        for title in ("Legacy Giving", "Stocks and Securities", "Donor-Advised Funds", "Employee Matching", "Cryptocurrency"):
            self.add(other, StandardPage(title=title, show_in_menus=True, eyebrow="Ways to Give",
                                         body=[("rich_text", r(f"How to give through {title.lower()}. (Sample text: add instructions or embed a third-party widget.)"))]))
        listings = {}
        listings["events"] = self.add(involved, ListingPage(title="Events", slug="events", kind="events", show_in_menus=True, eyebrow="Get Involved"))
        self.add(involved, StandardPage(title="Start a Fundraiser", slug="fundraise", show_in_menus=True, eyebrow="Get Involved",
                                        hero_intro="Turn your birthday, race or celebration into life-saving care.",
                                        body=[("cta_band", {"heading": "Create your fundraising page", "text": "It takes five minutes.", "link": {"label": "Start now", "page": None, "url": "/fundraise/start/"}})]))
        self.add(involved, StandardPage(title="Corporate Partners", slug="corporate-partners", show_in_menus=True, eyebrow="Get Involved",
                                        body=[("rich_text", r("Partner with us through cause marketing, employee giving and in-kind support. (Sample text.)"))]))
        listings["jobs"] = self.add(involved, ListingPage(title="Work With Us", slug="careers", kind="jobs", show_in_menus=True, eyebrow="Get Involved"))
        listings["tenders"] = self.add(involved, ListingPage(title="Open Tenders", slug="open-tenders", kind="tenders", show_in_menus=False, eyebrow="Get Involved"))
        self.add(involved, StandardPage(title="Email Signup", slug="email-signup", show_in_menus=True, eyebrow="Get Involved",
                                        body=[("newsletter", {"heading": "Join our community", "text": "Field updates and stories of hope."})]))
        self.add(involved, StandardPage(title="Global Ambassadors", slug="global-ambassadors", show_in_menus=False, eyebrow="Get Involved",
                                        body=[("rich_text", r("Our ambassadors lend their voices to people in crisis. (Sample text.)"))]))
        return gifts, listings

    def fill_get_involved(self, involved, gifts, listings):
        involved.body = [
            ("section_links", {"heading": "", "items": [
                {"icon": "heart", "title": "Give monthly", "text": "Join our community of monthly supporters.", "link": {"label": "Give monthly", "page": None, "url": "/donate/?frequency=monthly&appeal=GET-INVOLVED"}},
                {"icon": "gift", "title": "Give once", "text": "Make a one-time gift today.", "link": {"label": "Donate", "page": None, "url": "/donate/?appeal=GET-INVOLVED"}}]}),
            ("tabs", {"heading": "Ways to give", "tabs": [
                {"title": "Gifts catalog", "body": r("Symbolic gifts with an e-card for someone you love."), "image": self.photo(dp.CARDS["Gifts catalog"]), "link": {"label": "Browse gifts", "page": gifts, "url": ""}},
                {"title": "Tribute giving", "body": r("Give in honour or memory of someone special. Tick 'Dedicate this gift' when you donate."), "image": self.photo(dp.CARDS["Tribute giving"]), "link": {"label": "Give a tribute gift", "page": None, "url": "/donate/?appeal=TRIBUTE"}},
                {"title": "Planned giving", "body": r("Leave a gift in your will. (Sample text.)"), "image": self.photo(dp.CARDS["Planned giving"]), "link": {"label": "", "page": None, "url": ""}},
                {"title": "Stocks", "body": r("Give appreciated stocks and securities. (Sample text.)"), "image": self.photo(dp.CARDS["Stocks"]), "link": {"label": "", "page": None, "url": ""}}]}),
            ("section_links", {"heading": "Even more ways to help", "items": [
                {"icon": "calendar", "title": "Events", "text": "Join a gala, a fun run or a community event.", "link": {"label": "See events", "page": listings["events"], "url": ""}},
                {"icon": "megaphone", "title": "Start a fundraiser", "text": "Ask friends to give for your birthday or a challenge.", "link": {"label": "Start fundraising", "page": None, "url": "/fundraise/start/"}},
                {"icon": "handshake", "title": "Corporate partners", "text": "Make your business a force for good.", "link": {"label": "Partner with us", "page": None, "url": "/get-involved/corporate-partners/"}},
                {"icon": "globe", "title": "Use your voice", "text": "Follow us and share stories from the field.", "link": {"label": "Follow us", "page": None, "url": "https://example.org"}},
                {"icon": "mail", "title": "Stay informed", "text": "Get updates in your inbox.", "link": {"label": "Sign up", "page": None, "url": "/get-involved/email-signup/"}},
                {"icon": "briefcase", "title": "Work with us", "text": "Join our teams in the field and at headquarters.", "link": {"label": "See jobs", "page": listings["jobs"], "url": ""}}]}),
        ]
        self.republish(involved)

    def make_legal(self, home):
        legal = {}
        for title, slug in [("Privacy Policy", "privacy-policy"), ("Cookie Policy", "cookie-policy"), ("Terms and Conditions", "terms"), ("Fraud Alert", "fraud-alert")]:
            text = "Sample legal text. Have this page written or reviewed by a lawyer before launch."
            if slug == "fraud-alert":
                text = "We will never ask you to send money to a personal account. The only bank accounts we use for donations are the ones shown on this website's donate page. If anyone contacts you with different bank details, do not pay and report it to us."
            legal[slug] = self.add(home, StandardPage(title=title, slug=slug, show_in_menus=False, show_section_badges=False,
                                                      body=[("rich_text", r(text))]))
        return legal

    # --- settings and menus ----------------------------------------------------------------------

    def make_settings(self, home, who, what, www, stories_index, involved, history, leadership, reports_page, faq, contact,
                      emergencies_index, our_work, gifts, listings, legal):
        org = OrganisationSettings.load()
        org.name = "Haven Medical Relief"
        org.tagline = "Care that reaches every corner."
        org.hq_address = "12 Sample Street\nVictoria Island, Lagos\nNigeria"
        org.main_phone = "+234 1 000 0000"
        org.general_email = "info@example.org"
        org.donation_hotline = "+234 800 000 0000"
        org.donations_email = "donate@example.org"
        org.media_email = "media@example.org"
        org.facebook_url = "https://facebook.com/example"
        org.x_url = "https://x.com/example"
        org.instagram_url = "https://instagram.com/example"
        org.tax_id = "SAMPLE-0000"
        org.licence_note = "Text on this site is sample content."
        org.default_share_image = self.photo(dp.SHARE_IMAGE)
        org.privacy_page, org.cookie_page, org.terms_page, org.fraud_page = legal["privacy-policy"], legal["cookie-policy"], legal["terms"], legal["fraud-alert"]
        org.faq_page, org.stories_page, org.emergencies_page, org.where_we_work_page = faq, stories_index, emergencies_index, www
        org.mail_donation_form = self.make_pdf("Donate by post form")
        org.save()

        ds = DonationSettings.load()
        ds.notify_email = "finance@example.org"
        ds.save()

        def link(label, page=None, url="", children=None):
            return {"label": label, "page": page, "url": url, "children": children or []}

        def card(title, text, page=None, url="", image=None, button="Learn more"):
            return {"title": title, "text": text, "page": page, "url": url, "image": image, "button_label": button}

        ways = StandardPage.objects.get(slug="other-ways-to-give")
        nav = NavigationSettings.load()
        nav.header_menu = [
            ("item", {"label": "Who We Are", "page": who, "panel": "cards", "left_links": [
                link("Mission", self.mission), link("Our History", history), link("Leadership", leadership), link("Our Values", self.values),
                link("Accountability & Reports", reports_page), link("Ethics", page=StandardPage.objects.get(slug="ethics")),
                link("FAQ", faq), link("Contact Us", contact)],
                "promo_cards": [card("Watch our story", "Two minutes on what we do.", page=who, image=self.photo(dp.CARDS["Watch our story"]), button="Watch"),
                                card("Global Ambassadors", "The voices behind our mission.", url="/get-involved/global-ambassadors/", image=self.photo(dp.CARDS["Global Ambassadors"])),
                                card("Our History", "From volunteers to a global force.", page=history, image=self.photo(dp.CARDS["Our History"]))]}),
            ("item", {"label": "What We Do", "page": what, "panel": "emergencies", "left_links": [
                link("Our Approach", page=StandardPage.objects.get(slug="our-approach")),
                link("Our Work", our_work, children=[{"label": pg.title, "page": pg, "url": ""} for pg in self.programs]),
                link("Emergencies", emergencies_index), link("Training", page=StandardPage.objects.get(slug="training")),
                link("Research", page=StandardPage.objects.get(slug="research")), link("Partnerships", page=StandardPage.objects.get(slug="partnerships"))],
                "promo_cards": []}),
            ("item", {"label": "Where We Work", "page": www, "panel": "regions", "left_links": [link("View full map", www, url="")], "promo_cards": []}),
            ("item", {"label": "Stories and News", "page": stories_index, "panel": "stories", "left_links": [
                link("Stories", url="/stories-and-news/?type=story"), link("Videos", url="/stories-and-news/?type=video"),
                link("Media Center", page=StandardPage.objects.get(slug="media-center"))], "promo_cards": []}),
            ("item", {"label": "Get Involved", "page": involved, "panel": "cards", "left_links": [
                link("Donate", url="/donate/?appeal=MENU"), link("Give Monthly", url="/donate/?frequency=monthly&appeal=MENU"),
                link("Gifts of Hope", gifts), link("Email Signup", page=StandardPage.objects.get(slug="email-signup")),
                link("Other Ways to Give", ways, children=[{"label": c.title, "page": c, "url": ""} for c in ways.get_children().specific()]),
                link("Corporate Partners", page=StandardPage.objects.get(slug="corporate-partners")),
                link("Start a Fundraiser", url="/fundraise/start/"), link("Events", listings["events"]), link("Work With Us", listings["jobs"])],
                "promo_cards": [card("Donate", "Give now to rush relief.", url="/donate/?appeal=MENU", image=self.photo(dp.CARDS["Donate"]), button="Donate"),
                                card("Gifts of Hope", "Gifts that change lives.", page=gifts, image=self.photo(dp.CARDS["Gifts of Hope"])),
                                card("Get Involved", "Fundraise, volunteer, speak up.", page=involved, image=self.photo(dp.CARDS["Get Involved"])),
                                card("Honour & Memorial Giving", "Celebrate someone special.", url="/donate/?appeal=TRIBUTE", image=self.photo(dp.CARDS["Honour & Memorial Giving"]))]}),
        ]

        def col_link(label, page=None, url=""):
            return {"label": label, "page": page, "url": url}

        nav.footer_columns = [
            ("column", {"heading": "Get Involved", "links": [col_link("Donate", url="/donate/?appeal=FOOTER"), col_link("Give Monthly", url="/donate/?frequency=monthly&appeal=FOOTER"),
                                                              col_link("Gifts of Hope", gifts), col_link("Start a Fundraiser", url="/fundraise/start/"), col_link("Events", listings["events"])]}),
            ("column", {"heading": "Who We Are", "links": [col_link("Mission", self.mission), col_link("Our History", history), col_link("Leadership", leadership),
                                                            col_link("Financial Reports", reports_page), col_link("Contact Us", contact)]}),
            ("column", {"heading": "What We Do", "links": [col_link(pg.title, pg) for pg in self.programs[:5]] + [col_link("Emergencies", emergencies_index)]}),
        ]
        nav.legal_links = [("link", col_link("Privacy Policy", legal["privacy-policy"])), ("link", col_link("Cookie Policy", legal["cookie-policy"])),
                           ("link", col_link("Terms", legal["terms"])), ("link", col_link("Fraud Alert", legal["fraud-alert"])),
                           ("link", col_link("Open Tenders", listings["tenders"]))]
        nav.save()
