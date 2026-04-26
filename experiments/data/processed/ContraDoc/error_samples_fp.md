# False-positive samples (cascade flagged, not in gold) - sorted by LLM confidence
Reviewer: tag each as **(A) annotation gap** / **(B) topical overlap** / **(C) LLM hallucination**

## conf = high  -  type = Negation  -  doc = 3488771837_3
- A [sid=2]: Biographers have been uninterested in The Kempton-Wace Letters Writer Jack London wrote "Wace's" letters, and Anna Strunsky wrote "Kempton's."
- B [sid=16]: "Biographers have been intrigued by The Kempton-Wace Letters for the light it seems to shed on Jack London's life and ideas.
- NLI-FT P(contra) = 0.958
- LLM reason: Sentence A states biographers have been "uninterested" in The Kempton-Wace Letters, while Sentence B states biographers have been "intrigued" by it — these are directly opposing stances toward the same subject.
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Numeric  -  doc = 3503017441_5
- A [sid=17]: WASP - 44 has a mass that is 0. 951 times that of the Sun.
- B [sid=19]: WASP - 44 has an effective temperature of 5410 K , cooler than the Sun.WASP - 44 has a mass that is 1.2 times that of the Sun.
- NLI-FT P(contra) = 0.950
- LLM reason: Both sentences describe the mass of WASP-44 relative to the Sun, but Sentence A states it is 0.951 solar masses while Sentence B states it is 1.2 solar masses — these are incompatible numeric values for the same attribute of the same entity.
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Content  -  doc = 3502252168_1
- A [sid=11]: Capel Lligwy is a well-preserved chapel near Rhos Lligwy in Anglesey, north Wales, dating back to the first half of the 12th century.
- B [sid=46]: It notes that " the wheel has turned full circle and Capel Lligwy today is just another ruined relic of a former age. "
- NLI-FT P(contra) = 0.950
- LLM reason: Sentence A describes Capel Lligwy as "well-preserved," while Sentence B characterizes it as "just another ruined relic," directly contradicting the state/condition of the same chapel.
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Content  -  doc = 3499318678_1
- A [sid=27]: However , for a mid - series section ( that is , a section from halfway through a series element to halfway through the next series element ) will have the same image impedance on both ports due to symmetry.
- B [sid=31]: The image impedance of the half - section is dissimilar on the input and output ports : on the side presenting the series element it is equal to the mid - series ZiT , but on the side presenting the shunt element it is equal to the mid - shunt ZiΠ.
- NLI-FT P(contra) = 0.950
- LLM reason: Sentence A states that a mid-series section has the same image impedance on both ports (due to symmetry), while Sentence B states that the half-section has dissimilar (different) image impedances on its input and output ports, directly contradicting the claim of equal impedances on both ports.
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Content  -  doc = 3499318678_3
- A [sid=27]: However , for a mid - series section ( that is , a section from halfway through a series element to halfway through the next series element ) will have the same image impedance on both ports due to symmetry.
- B [sid=31]: The image impedance of the half - section is dissimilar on the input and output ports : on the side presenting the series element it is equal to the mid - series ZiT , but on the side presenting the shunt element it is equal to the mid - shunt ZiΠ.
- NLI-FT P(contra) = 0.950
- LLM reason: Sentence A states that a mid-series section has the same image impedance on both ports (due to symmetry), while Sentence B states that the half-section (which is structurally equivalent) has dissimilar image impedances on its input and output ports, contradicting the claim of equal impedances on both sides.
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Content  -  doc = 3499318678_5
- A [sid=27]: However , for a mid - series section ( that is , a section from halfway through a series element to halfway through the next series element ) will have the same image impedance on both ports due to symmetry.
- B [sid=31]: The image impedance of the half - section is dissimilar on the input and output ports : on the side presenting the series element it is equal to the mid - series ZiT , but on the side presenting the shunt element it is equal to the mid - shunt ZiΠ.
- NLI-FT P(contra) = 0.950
- LLM reason: Sentence A states that the mid-series section has the same image impedance on both ports (due to symmetry), while Sentence B states that the half-section (which presents the mid-series ZiT on one side) has dissimilar image impedances on its two ports, contradicting the claim of equal impedance on both ports.
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Content  -  doc = 3499318678_8
- A [sid=26]: However , for a mid - series section ( that is , a section from halfway through a series element to halfway through the next series element ) will have the same image impedance on both ports due to symmetry.
- B [sid=30]: The image impedance of the half - section is dissimilar on the input and output ports : on the side presenting the series element it is equal to the mid - series ZiT , but on the side presenting the shunt element it is equal to the mid - shunt ZiΠ.
- NLI-FT P(contra) = 0.950
- LLM reason: Sentence A states that a mid-series section has the same image impedance on both ports (due to symmetry), while Sentence B states that the half-section has dissimilar image impedances on its input and output ports, which directly contradicts the claim of equal impedances on both ports.
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Numeric  -  doc = 3503017441_6
- A [sid=18]: WASP - 44 has an effective temperature of 6000 K , hotter than the Sun.
- B [sid=23]: WASP - 44 has an effective temperature of 5410 K , cooler than the Sun.
- NLI-FT P(contra) = 0.950
- LLM reason: Both sentences describe the effective temperature of the same star (WASP-44) but assert incompatible values (6000 K vs. 5410 K) and opposite comparisons to the Sun (hotter vs. cooler).
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Numeric  -  doc = 3499318689_10
- A [sid=4]: The game 's 55 levels include power - ups , bonus rounds , and minigames.
- B [sid=13]: Each of the game 's eleven stages include five rounds of increasingly complex block patterns for Kirby to clear.
- NLI-FT P(contra) = 0.948
- LLM reason: Sentence A states the game has 55 levels, while Sentence B implies 55 rounds total (11 stages × 5 rounds), but describes the structure as 11 stages with 5 rounds each — directly conflicting with Sentence A's claim of 55 undivided "levels," and more critically, the two sentences present incompatible structural counts: 55 levels vs. 11 stages as the primary unit of progression.
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Content  -  doc = 3488771867_6
- A [sid=11]: This situation leaves Carthoris in a predicament.
- B [sid=12]: As Thuvia suffers the common Burroughsian heroine's fate of being kidnapped and in need of rescue, Carthoris' goal is abetted by circumstances.
- NLI-FT P(contra) = 0.947
- LLM reason: Sentence A states that the situation leaves Carthoris in a predicament (i.e., circumstances work against him), while Sentence B states that Carthoris' goal is abetted (i.e., helped/furthered) by circumstances — these two descriptions of how the situation affects Carthoris are mutually incompatible.
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Content  -  doc = 3503017493_6
- A [sid=4]: The highway connects the city of Hope to the Seward Highway , and travels through 17 miles ( 27 km ) of the Chugach National Forest.
- B [sid=16]: The entire length of the Hope Highway is located in the Chugach National Forest.
- NLI-FT P(contra) = 0.947
- LLM reason: Sentence A states the highway travels through only 17 miles (27 km) of the Chugach National Forest (implying only a portion is within the forest), while Sentence B claims the entire length of the Hope Highway is located in the Chugach National Forest — these two claims are mutually incompatible.
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Content  -  doc = 3489738278_5
- A [sid=15]: At least 2,466 people globally are confirmed to have been handed the sentence last year, an increase of 28% compared with 2013.Sub-Saharan Africa saw a 28% increase in reported cases The report notes that the spike in sentencing is attributable to mass-sentencing in countries including Egypt and Nigeria, "against scores of people in some cases."
- B [sid=18]: Sub-Saharan Africa, for example, saw a 28% fall in reported cases, and executions recorded in the Middle East and North Africa were down 23% compared to 2013.
- NLI-FT P(contra) = 0.946
- LLM reason: Both sentences describe the change in Sub-Saharan Africa's reported cases, but Sentence A states there was a 28% **increase** while Sentence B states there was a 28% **fall**, which are directly incompatible claims about the same entity and metric.
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Perspective/View/Opinion  -  doc = 3499318680_2
- A [sid=51]: QuackShot was released to mostly negative reviews from video game journalists.
- B [sid=53]: QuackShot received a mostly positive response from critics upon release.
- NLI-FT P(contra) = 0.946
- LLM reason: Both sentences describe the critical reception of QuackShot upon release, but assert opposite evaluations — Sentence A states it was "mostly negative" while Sentence B states it was "mostly positive."
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Numeric  -  doc = 3499318685_1
- A [sid=25]: On 18 May 1991 , the Zrinski Battalion was established as a special forces unit of the ZNG.
- B [sid=32]: The Zrinski Battalion was established in Kumrovec on 18 May 1989.
- NLI-FT P(contra) = 0.945
- LLM reason: Both sentences describe the establishment of the same entity (the Zrinski Battalion) on the same date (18 May) but in different years — 1991 in Sentence A versus 1989 in Sentence B — which is a direct numeric contradiction.
- *(reviewer tag: A / B / C)*

---
## conf = high  -  type = Numeric  -  doc = 3499318683_2
- A [sid=1]: = Chad at the 2008 Summer Olympics =
- B [sid=3]: The appearance of this delegation marked the first appearance of Chad at the Summer Olympics , the first been in 1964 Summer Olympics in Tokyo , Japan , and its seventh appearance since its Olympic hiatus between 1976 and 1980.
- NLI-FT P(contra) = 0.944
- LLM reason: Sentence B contradicts itself and the context of Sentence A: it says the 2008 appearance "marked the first appearance of Chad at the Summer Olympics" while simultaneously stating "its seventh appearance," which are mutually exclusive claims about the same delegation's appearance count.
- *(reviewer tag: A / B / C)*

---
