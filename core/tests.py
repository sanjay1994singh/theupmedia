from django.test import SimpleTestCase, TestCase
from django.urls import reverse


class AdSenseVerificationTests(SimpleTestCase):
    publisher_id = "2037181352494119"

    def test_ads_txt_is_available_at_site_root(self):
        response = self.client.get(reverse("core:ads_txt"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        self.assertEqual(
            response.content.decode(),
            f"google.com, pub-{self.publisher_id}, DIRECT, f08c47fec0942fa0\n",
        )


class TrustPageTests(TestCase):
    def test_trust_pages_are_available(self):
        for route_name in (
            "core:about",
            "core:contact",
            "core:privacy_policy",
            "core:terms",
            "core:disclaimer",
            "core:editorial_policy",
            "core:fact_checking_policy",
            "core:corrections_policy",
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
