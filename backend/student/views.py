import pytz
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from backend.Google import spreadsheet_get_data, spreadsheet_append, spreadsheet_delete_row, spreadsheet_top_insert
from .serializers import School, SchoolSerializer, Exam, Subject, Question, Choice, Result, \
    ResultsSerializer, SchoolListSerializer, StudentApplied, NotificationSerializer
from rest_framework.views import APIView
from .models import ResultDetails, CourseRecommended
from accounts.models import Student
from datetime import timedelta, datetime
from django.utils import timezone
from rest_framework import filters
from rest_framework.permissions import IsAuthenticated
import pandas as pd
import numpy as np
from django.db.models import Q, Prefetch, Count

class SchoolList(generics.ListAPIView, generics.UpdateAPIView):
    serializer_class = SchoolListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        s = None
        status_ = self.request.query_params.get('status')
        if status_ is None or s == 'None':
            s = None
        else:
            s = status_
        #return School.objects.exclude(pk__in=res, applied_school__status='Accepted').prefetch_related('applied_school')
        res = Result.objects.filter(student__user_id=self.request.user.id, submitted=True).select_related('school', 'student').values_list('school_id')
        if status_ is None or s == 'None':
            student_applied = StudentApplied.objects.filter(student__user_id=self.request.user.id).values_list('school_id')
            '''
            return School.objects.filter(Q(applied_school__isnull=True) & Q(school_exam__is_published=True) &
                                         Q(applied_school__student__user_id=self.request.user.id)
                                         )
             '''
            return School.objects.filter(school_exam__is_published=True).exclude(pk__in=student_applied)
        else:
            return School.objects.filter(Q(applied_school__status=s) & Q(school_exam__is_published=True)
                                         & Q(applied_school__student__user_id=self.request.user.id)
                                 ).prefetch_related('applied_school').exclude(pk__in=res)

    def update(self, request, *args, **kwargs):
        student = Student.objects.get(user_id=self.request.user.id)
        data = request.data
        if 'id' in request.data and 'apply' in request.data:
            try:
                s = StudentApplied.objects.get(school_id=data['id'], student=student)
                s.status = 'Pending'
                s.save()
            except StudentApplied.DoesNotExist:
                school = School.objects.get(id=data['id'])
                StudentApplied.objects.create(school=school, student=student, status='Pending')
        elif 'id' in request.data and 'cancel' in request.data:
            StudentApplied.objects.get(school_id=data['id'], student=student).delete()
        else:
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return Response(status=status.HTTP_200_OK)

class StartExamApi(APIView):
    def get(self, request, format=None, **kwargs):
        try:
            exam = School.objects.prefetch_related(
                Prefetch(
                    'school_exam__exam_subjects__subject_questions',
                    queryset=Question.objects.filter().prefetch_related('question_choices').order_by('?'),
                )
            ).get(id=kwargs['pk'])
            serializer = SchoolSerializer(exam)
            data = serializer.data

            result = Result.objects.get(school=exam, student__user_id=request.user.id)
            data['date_taken'] = result.date_taken
            data['date_end'] = result.date_end
            data['video'] = result.video
            data['submitted'] = result.submitted
            data['student_name'] = request.user.name
        except (Exception,):
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, format=None, **kwargs):
        if 'start' not in request.data:
            return Response(status=status.HTTP_204_NO_CONTENT)

        student = Student.objects.get(user_id=request.user.id)
        try:
            exam = Exam.objects.get(school_id=kwargs['pk'])
            school = School.objects.get(pk=kwargs['pk'])
            time_limit = exam.time_limit.split(':')
            hours = int(time_limit[0])
            minutes = int(time_limit[1])
        except School.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            # Check if result exist
            result = Result.objects.get(student=student, school=school)
            result.video = request.data['start']
            result.save()
        except Result.DoesNotExist:
            # Create if not
            date_end = datetime.now(tz=timezone.utc) + timedelta(hours=hours) + timedelta(minutes=minutes)
            Result.objects.create(student=student,
                                  school=school,
                                  date_taken=datetime.now(tz=timezone.utc),
                                  video=request.data['start'],
                                  date_end=date_end)

        return Response(status=status.HTTP_200_OK)


class SubmitResultDetails(APIView):
    def post(self, request, format=None, **kwargs):
        try:
            data = request.data
            school = School.objects.select_related('school_exam').get(id=kwargs['pk'])
            result = Result.objects.get(school=school, student__user=request.user)
            result.video = data['video_id']
            result.tab_switch = data['tab_switch']
            result.save()

            return Response(status=status.HTTP_200_OK)
        except (Exception,):
            return Response(status=status.HTTP_200_OK)
'''
(0, 'multipleChoice'),
(1, 'checkbox'),
(2, 'fillInTheBlank'),
'''
class SubmitExamApi(APIView):
    def post(self, request, format=None, **kwargs):
        school = School.objects.select_related('school_exam').get(id=kwargs['pk'])
        student = Student.objects.get(user=request.user)
        result = Result.objects.get(school=school, student=student)

        if ResultDetails.objects.filter(result=result).count() or result.submitted:
            return Response(status=status.HTTP_200_OK)

        result.submitted = True
        result.save()

        subjects = Subject.objects.filter(exam__school=school)
        rd = request.data
        for subject in subjects:
            if subject.name in request.data:
                score = 0
                for d in rd[subject.name]:
                    if d is not None:
                        q = Question.objects.get(id=d['id'])
                        if q.type == 0:
                            if Choice.objects.get(id=d['answer']).correct == 'true':
                                score += q.score
                        if q.type == 1:
                            for ans in d['answer']:
                                if Choice.objects.get(id=ans).correct == 'true':
                                    score += q.score
                        if q.type == 2:
                            for ans in d['answer']:
                                if ans is not None:
                                    # list of answers
                                    la = Choice.objects.get(question=q).correct.split(',')
                                    if ans in la:
                                        score += q.score
                        if q.type == 3:
                            if d['answer']:
                                choice = Choice.objects.get(id=d['answer']).correct
                                score += int(choice)
                ResultDetails.objects.create(
                    result=result,
                    score=score,
                    subject=subject,
                )
        # result.submitted = True
        result.save()


        overall_score = 0
        # Subject/35 Subject/35
        subject_header_list = []
        student_scores = []
        items_append_spreadsheet = []

        # Regression
        ex = Exam.objects.get(school=school)
        data = pd.read_csv(ex.csv_file).sort_values(by='Overall', ascending=False, ignore_index=True)
        # values = pd.DataFrame(data, columns=['Course', 'Overall'])

        regression_model = "y = "
        formula = "y = &beta;0"
        beta_count = 1
        try:
            x_drops = ['Course', 'Strand', 'Student', 'Overall']

            x = data.drop(x_drops, axis='columns')
            x = np.array(x)
            col_length = np.size(x, 0)
            ones = np.ones((col_length, 1))
            x = np.hstack((ones, x))
            y = np.array(data['Overall'])

            result_d = ResultDetails.objects.filter(result=result)
            skip_col = 3
            j = 0
            for col in data.columns:
                if j >= skip_col and col != 'Overall':
                    for r in result_d:
                        subject_s_total = col.split('/')
                        if r.subject == subject_s_total[0]:
                            student_scores.append(r.score)
                            overall_score += r.score
                            formula += " + &beta;"+ str(beta_count) +"("+ r.subject +")"
                            beta_count += 1
                            over_score = int(subject_s_total[1])
                            r.overall = over_score
                            # for spreadsheet
                            subject_header_list.append(r.subject+'/'+str(over_score))
                            r.save()
                j += 1

            predicted = 0
            '''
            xt = x.transpose()
            a = np.dot(xt, x)
            b = np.dot(xt, y)
            beta = np.linalg.solve(a, b)
            '''
            xt = x.transpose()
            a = np.dot(xt, x)
            k = np.linalg.inv(a)
            beta = np.dot(np.dot(k, xt), y)

            for i, b in enumerate(beta):
                if i == 0:
                    predicted += b
                    regression_model += str(b)
                else:
                    predicted += (b * student_scores[i - 1])
                    regression_model += ' + (' + str(b) + '*' + str(student_scores[i - 1]) + ')'
            predicted = round(predicted)
            regression_model += '<br/> y = ' + str(predicted)

            values = pd.DataFrame(data, columns=['Course', 'Overall']).query("Overall <= " + str(predicted))
            '''
            last_rank = 1
            last_overall = -1
            for j in range(10):
                for index, row in values.iterrows():
                    if last_overall == -1:
                        last_overall = int(row['Overall'])
                    else:
                        if last_overall != int(row['Overall']):
                            last_rank += 1

                    if j == 0:
                        exam_info['Course'] = row['Course']

                    CourseRecommended.objects.create(
                        result=result,
                        course=row['Course'],
                        rank=last_rank,
                    )
                    last_overall = int(row['Overall'])
                    values = values.drop(values[values['Course'] == row['Course']].index)
                    break
            '''
            recommendation_count = 0
            last_recommended_value = 0
            rank = 0

            while True:
                last_overall = 0
                course = ""
                for index, row in values.iterrows():

                    last_overall = int(row['Overall'])
                    values = values.drop(values[values['Course'] == row['Course']].index)
                    #recommendation_count += 1
                    course = row['Course']
                    break

                if last_overall != last_recommended_value and recommendation_count >= 10 or course == "":
                    break
                else:
                    if last_overall != last_recommended_value:
                        rank += 1
                CourseRecommended.objects.create(
                    result=result,
                    course=course,
                    rank=rank,
                )
                # for spreadsheet
                if rank == 1:
                    items_append_spreadsheet.append([student.id, course, student.strand]
                                                    + student_scores + [overall_score])
                recommendation_count += 1
                last_recommended_value = last_overall
            result.regression_model = regression_model
            result.formula = formula
            result.save()
        except (Exception,):
            pass


        spreadsheet_append(ex.spreadsheet_id, items_append_spreadsheet)

        '''
        if exam_info['Course'] != '':
            df = pd.DataFrame(exam_info)
            df.to_csv(ex.csv_file.path, mode='a', index=False, header=False)
        else:
            course = data.iloc[[0, -1]]['Course'][data[data.columns[0]].count()-1]
            exam_info['Course'] = course
            CourseRecommended.objects.create(
                result=result,
                course=course,
                rank=1,
            )
            regression_model = "y = 0 "
            for i in range(beta_count):
                regression_model += " + 0(0)"

            result.formula = formula
            result.regression_model = regression_model
            result.save()
            df = pd.DataFrame(exam_info)
            df.to_csv(ex.csv_file.path, mode='a', index=False, header=False)
        '''
        '''
        csv_file = Exam.objects.get(school=school).csv_file
        data = pd.read_csv(csv_file)
        strand = request.user.student_user.strand
        predictors = []
        result_d = ResultDetails.objects.filter(result=result)
        try:
            skip_col = 2
            j = 0
            for col in data.columns:
                if j >= skip_col:
                    for r in result_d:
                        if r.subject == col:
                            predictors.append(r.score)
                j += 1
        except (Exception,):
            return Response({ 'status': '-1' }, status=status.HTTP_200_OK)
        dummies = pd.get_dummies(data['Strand'])
        for s in dummies.columns.values:
            if s == strand:
                predictors.append(1)
            else:
                predictors.append(0)
        merged = pd.concat([data, dummies], axis='columns')
        merged = merged.drop(['Course', 'Strand'], axis='columns')

        c = data['Course'].values
        course = [i for i in c]
        y = [i for i in range(len(c))]
        drop = [-1]

        for i in range(10):
            if len(y) <= 0:
                break

            if drop[0] != -1:
                merged = merged.drop(drop, axis='rows').reset_index(drop=True)
                course.pop(drop[0])

            x = merged.values
            model = LinearRegression()
            model.fit(x, y)
            r2 = (model.score(x, y))
            p = model.predict([predictors])

            y.pop()
            predicted = round(p[0])
            if predicted >= len(y)-1:
                drop[0] = len(y)-1
            elif predicted <= 0:
                drop[0] = 0
            else:
                drop[0] = predicted
            CourseRecommended.objects.create(
                result=result,
                course=course[drop[0]],
                r2=r2
            )
        '''

        return Response(status=status.HTTP_200_OK)

class ResultApi(APIView):
    def get(self, request, format=None, **kwargs):
        try:
            data = dict()
            school = School.objects.select_related('school_exam').get(id=kwargs['pk'])
            data['name'] = school.name
            data['description'] = school.description
            try:
                data['logo_url'] = school.logo.url
            except AttributeError:
                data['logo_url'] = None

            result = Result.objects.get(school=school, student__user_id=request.user.id)
            data['date_taken'] = result.date_taken
            data['date_end'] = result.date_end
            data['formula'] = result.formula
            data['regression_model'] = result.regression_model
            data['submitted'] = result.submitted
            result_list = []
            course_r_list = []
            if result.submitted:
                for r in ResultDetails.objects.filter(result=result):
                    obj = {
                        'id': r.id,
                        'subject': r.subject,
                        'score': r.score,
                        'total': r.overall
                    }
                    #Subject.objects.select_related('exam', 'exam__school').get(exam__school_id=kwargs['pk'], name=r.subject).total_questions
                    result_list.append(obj)
                for r in CourseRecommended.objects.filter(result=result):
                    obj = {
                        'id': r.id,
                        'course': r.course,
                        'rank': r.rank,
                    }
                    course_r_list.append(obj)
            data['result_details'] = result_list
            data['course_recommended'] = course_r_list
        except (Exception,):
            return Response({'not_found': '1'}, status=status.HTTP_200_OK)
        return Response(data)

class ResultsApi(generics.ListAPIView,):
    serializer_class = ResultsSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['school__name']

    def get_queryset(self):
        user_id = self.request.user
        date_from = self.request.query_params.get('from')
        date_to = self.request.query_params.get('to')
        if date_from is not None and date_to is not None:
            date_from = datetime.strptime(date_from+" 00:00:00", "%Y-%m-%d %H:%M:%S")
            date_to = datetime.strptime(date_to+" 23:59:59", "%Y-%m-%d %H:%M:%S")
            asia_timezone = pytz.timezone('Asia/Shanghai')
            date_from = asia_timezone.localize(date_from)
            date_to = asia_timezone.localize(date_to)

            return Result.objects.filter(student__user=user_id,
                                         submitted=True,
                                         date_taken__range=[date_from, date_to])
        return Result.objects.filter(student__user=user_id, submitted=True)


#Notification
class Notification(APIView):
    def get(self, request, format=None, **kwargs):

        s = StudentApplied.objects.filter(~Q(status="Pending") & ~Q(status=None), student__user_id=self.request.user.id).select_related('school', 'student__user')
        data = dict()
        data['not_seen_count'] = s.filter(is_seen_by_student=False).count()
        data['count'] = s.count()
        return Response(data, status=status.HTTP_200_OK)

class NotificationDetailsPagination(PageNumberPagination):
    page_size = 3

    def get_paginated_response(self, data):
        return Response(data)

class NotificationDetails(generics.ListAPIView, generics.UpdateAPIView):
    serializer_class = NotificationSerializer
    pagination_class = NotificationDetailsPagination

    def get_queryset(self):
        return StudentApplied.objects.filter(
             ~Q(status="Pending") & ~Q(status=None),
            student__user_id=self.request.user.id
        ).select_related('school', 'student__user')


    def update(self, request, *args, **kwargs):
        data = request.data
        if 'read_all' in data:
            s = StudentApplied.objects.filter(student__user_id=self.request.user.id,
                                              is_seen_by_student=False).select_related('school')
            s.update(is_seen_by_student=True)
        if 'id' in data:
            try:
                s = StudentApplied.objects.get(id=data['id'], student__user_id=self.request.user.id)
                s.is_seen_by_student = True
                s.save()
            except StudentApplied.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_200_OK)

#Notification end


#School AvailableCourses
class AvailableCourses(APIView):
    def get(self, request, format=None, *args, **kwargs):
        try:
            data={}
            csv_file = Exam.objects.get(school_id=kwargs['pk']).csv_file
            csv = pd.read_csv(csv_file)
            data['courses'] = csv.Course.unique()
        except (Exception,):
            return Response({ 'status': '204' }, status=status.HTTP_200_OK)

        return Response(data, status=status.HTTP_200_OK)


# Dashboard Details
class DashboardDetails(generics.ListAPIView):

    def list(self, request):
        data = dict()
        school = School.objects.annotate(count=Count('school_result')).values('name', 'count').order_by()
        data['school'] = list(school)

        result = Result.objects.filter(student__user=request.user, submitted=True)[:5]
        result_list = []
        for r in result:
            course_list = []
            course = CourseRecommended.objects.filter(result=r)[:3]
            for c in course:
                d = {
                    'id': c.id,
                    'course': c.course,
                    'rank': c.rank,
                }
                course_list.append(d)
            d = {
                'id': r.id,
                'name': r.school.name,
                'course_list': course_list,
            }
            result_list.append(d)
        data['recent_result'] = result_list

        return Response(data, status=status.HTTP_200_OK)
