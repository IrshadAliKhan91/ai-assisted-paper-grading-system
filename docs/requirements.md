1.2 - Problem Statement
Even though other automated grading systems are suggested at present in the past years, they are still ineffective in gauging brief descriptive answers in schools. Most of them depend on keywords and solid patterns which do not appreciate the meaningfully similar responses. Nevertheless, teachers are still having excessive workloads and are unable always to deliver unbiased, timely assessments to hundreds of answer sheets. These systems too have difficulties with noisy text retrieved by scanned response and cannot be brought to bear on general science questions. Thus, the objective of this project is to develop an artificial intelligence-based short-answer grading system that can read the text in scanned materials, process it, compare it semantically with reference answers in a database and issue fair and consistent grades.

1.3 - Objectives
The limitations mentioned above are in line with the objectives of this project. Their emphasis is on designing, testing and analyzing a system that can be able to perform effectively in real academic conditions.
1) To read and extract short descriptive English answers in a response format (scanned answer sheets) and cleanse the text and prepare it to be compared. The discussion consists of the knowledge of changes in writing styles, common student mistakes, and linguistic composition of short general-science responses.
2) To create a grading mechanism which is semantically-similarity based and attempts to assess meaning as opposed to surface based keywords. The design takes into consideration the modern NLP embedding strategies to make sure that the students who use various words but share the same idea get the proper credit.
3) To perform variant testing in the case of different types of responses, variations in phrasing, and different writing quality, and a variety of general-science questions. This guarantees that the system is consistent in its response to various inputs of students and has a consistent response.

1.4 - Scope
An effective scope guarantees that the project is within manageable and attainable time. The project will be implemented in the form of a Phase-1 with definite boundaries.

1.4.1 Scope In
● Lifestyle assessments of short answers (2 to 3 lines only).
● Only responses in English language.
● Basic general science subjects (e.g., biology, physics fundamentals, and chemistry
fundamentals).
● Hofstede: It is accepted to receive scanned handwritten or printed answer sheets.
● Standard OCR extraction of text.
● Noise and normalization of text.
● Checking the responses of students against reference answers in a database.
● Semantically-based grading.
● Final marks generated against every student response.

1.4.2 Scope Out
● No long response, essays and long analytical responses.
● None of the multilingual assistance (English only).
● No higher subjects of science than general science.
● None of the diagram or formula recall.
● No mathematical formula breaking.
● No training on handwriting recognition.
● None of the training in a deep learning model at this stage (only the existing NLP
models were used).
● None of the external learning systems, including LMS systems.

1.5- Non-Functional and Functional Requirements.

1.5.1 Functional Requirements
FR01 – Input Upload
The system will enable the instructors to post scanned copies of student answer sheets.
FR02 – Text Extraction
The system will be able to extract the text on the scanned answer images by OCR.
FR03 – Text Preprocessing
The system will remove, standardize and correct extracted text in order to subject it to comparison.
FR04 – Key Answer Retrieval
The system will then retrieve the appropriate reference answer at a stored database according to the question.
FR05- Semantic Similarity Scoring.
The system will calculate the score of similarity between the answer given by the student and the reference answer.
FR06 – Grading Mechanism
The system will be able to mark students by mapping similarity scores to grades.
FR07 – Result Display
The system will show the final marks in the readable form.

1.5.2 Non-Functional Requirements.
NFR01 – Accuracy
The outcomes of similarity should be reasonably conceptually correct.
NFR02 – Consistency
The system should also be able to generate consistent grading results of similar answers.
NFR03 – Usability
The interface should be straightforward and easy to use by the instructors.
NFR04 – Performance
The grading performance should also be fast and preferably under seconds.
NFR05 – Scalability
The system should be in such a way that it can accommodate more subjects when it moves in its next stage.
NFR06 – Maintainability
It should be easy to edit the reference answers and grading thresholds.
NFR07 – Reliability
The system should be reliable when it is being continuously or batch processed.
