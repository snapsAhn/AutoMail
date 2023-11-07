#!/usr/bin/env python3

from jinja2 import Environment, PackageLoader, FileSystemLoader, select_autoescape
from account import MY_PW, MY_ID
from email.message import EmailMessage
from smtplib import SMTP_SSL
import time
import datetime
import pymysql
import sshtunnel
from email.utils import formataddr
import numpy
import sys
from datetime import date


day = time.strftime('%m월 %d일'.encode('unicode-escape').decode(), time.localtime(time.time())).encode().decode('unicode-escape')



queryTime = datetime.datetime.now()  - datetime.timedelta(minutes=10)
queryTimePlusOne = queryTime + datetime.timedelta(minutes=1)
queryTime_yesterday = queryTime  - datetime.timedelta(days = 1)
queryTime_yesterday_PlusOne = queryTime_yesterday + datetime.timedelta(minutes=1)
queryTime_oneweek = queryTime  - datetime.timedelta(days = 7)
nowToStr = queryTime.strftime("%Y-%m-%d %H:%M")
nowToStrPlusOne = queryTimePlusOne.strftime("%Y-%m-%d %H:%M")
yesterdayToStr = queryTime_yesterday.strftime("%Y-%m-%d %H:%M")
yesterdayToStrPlusOne = queryTime_yesterday_PlusOne.strftime("%Y-%m-%d %H:%M")
oneweekToStr = queryTime_oneweek.strftime("%Y-%m-%d %H:%M")


def is_busday(workdayStr):
    holidays_2022 = ['2022-01-23','2022-02-01','2022-02-02','2022-03-01','2022-03-09',
                '2022-05-05','2022-06-01','2022-06-06','2022-08-15','2022-09-09',
                '2022-09-12','2022-10-03','2022-10-10']
    holidays_2023 = ['2023-01-23', '2023-01-24','2023-03-01','2023-05-05','2023-06-06',
                    '2023-08-15','2023-09-28','2023-09-29','2023-10-03','2023-10-09','2023-12-25']

    bdd = numpy.busdaycalendar(weekmask='1111100', holidays=holidays_2023)
    return numpy.is_busday(workdayStr, busdaycal=bdd)

def today():
    today = str(date.today())
    return today





def send_template_email(template, to, subj, **kwargs):
    # jinja의 Environment 기능을 사용하여 template의 위치를 알려주기. 
    # module이 있으면 PackageLoader사용, 자체 모듈이 없으면 FileSystemLoader 사용.
    env = Environment(
        # loader=PackageLoader('project', 'email_templates'),
        loader=FileSystemLoader('email_templates'),
        autoescape=select_autoescape(['html', 'xml'])
    )

    # env 변수로 template 생성.
    template = env.get_template(template)

    # 최종 html을 만들어 render 방법을 사용하기. render()안에는 동적으로 전달될 kwargs를 사용할 수 있음. 
    html = template.render(**kwargs)
    #send_email 함수를 실행. 
    send_email(to, subj, html)


def send_email(to, subj, body):
    """Sends an email."""
    msg = EmailMessage()

    from_addr = formataddr(('msp_report', MY_ID))
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subj

    msg.set_content(body, subtype='html')

    with SMTP_SSL("smtp.gmail.com", 465) as smtp:
        # smtp.starttls()
        smtp.login(MY_ID, MY_PW)
        smtp.send_message(msg)
    
    #완료 메시지
    print("성공", sep="\t")
    
    



# DB에 저장되어 있는 자빅스 데이터를 쿼리하여 가져오는 코드
# SSH 터널링 하여 DB에 접속
def disk_dayreport(date, datePlusOne):
    with sshtunnel.SSHTunnelForwarder(
                            ('[DB IP]'),
                            ssh_username='[username]',
                            ssh_pkey='[DB Server Key]',
                            remote_bind_address=('[DB IP]', 3306),
                            ) as tunnel:
    # connect MySQL like local                           
        with pymysql.connect(
            host='127.0.0.1', #ssh 터널링을 통해 172.17.44.2의 입장이 되었으므로 localhost로 접속해줌
            user='[db user]]',
            passwd='[db password]',
            db='[db name]',
            charset='utf8',
            port=tunnel.local_bind_port,
            cursorclass=pymysql.cursors.DictCursor) as conn:
            with conn.cursor() as cur:
                sql_01 = """
                SELECT g.name as hostgroup ,hs.host, i.name, FROM_UNIXTIME(h.clock,'%Y-%m-%d %H:%i') as event_time , round(h.value, 2) as value
                FROM zabbix.hosts hs 
                INNER JOIN hosts_groups hg ON (hg.hostid = hs.hostid)
                INNER join hstgrp g on hg.groupid = g.groupid
                INNER JOIN items i ON hs.hostid = i.hostid
                INNER join history h ON h.itemid = i.itemid
                WHERE  g.name in('hmm_DB')
                and i.name like 'Used disk space on%'
                AND h.clock>=unix_timestamp('""" + date +"""')
                AND h.clock<=unix_timestamp('""" + datePlusOne + """')
                and h.value > 80
                order by h.value desc, hostgroup;
                
                """ 
                # print(sql_01)

                sql_02 = """
                SELECT g.name as hostgroup, hs.host, i.name, FROM_UNIXTIME(h.clock,'%Y-%m-%d %H:%i') as event_time , round(h.value, 2) as value
                FROM hosts hs 
                INNER JOIN hosts_groups hg ON (hg.hostid = hs.hostid)
                INNER join hstgrp g on hg.groupid = g.groupid
                INNER JOIN items i ON hs.hostid = i.hostid
                INNER join history h ON h.itemid = i.itemid
                WHERE  g.name in('hmm_Linux', 'hmm_SOACS', 'hmm_WAS', 'hmm_Windows' , 'hmm_WASMain' , 'hmm_Citrix_HyperV', 'hmm_Citrix_XenApp', 'hmm_DR_KeepRunning', 'hmm_DWP', 'hmm_GAUS', 'hmm_CTX_HyperV', 'hmm_CTX_XenApp')  
                and i.name like 'Used disk space on%(percentage)'
                AND h.clock>=unix_timestamp('""" + date +"""')
                AND h.clock<=unix_timestamp('""" + datePlusOne + """')
                AND h.value > 70
                order by hostgroup , h.value desc ;
                """ 
                # print(sql_02)

                cur.execute(sql_01)
                result_list1 = cur.fetchall()
                if type(result_list1) == tuple : # 조회된 결과가 없을 때 list로 타입 설정 
                    result_list1 = list()

                cur.execute(sql_02)
                result_list2 = cur.fetchall()
                if type(result_list2) == tuple :
                    result_list2 = list()
                disk_result_all = result_list1 + result_list2
                # print(result_all)
                # result_all_len = len(result_all)

                return disk_result_all
            
def error_dayreport():
    with sshtunnel.SSHTunnelForwarder(
                            ('[db ip]'),
                            ssh_username='[username]]',
                            ssh_pkey='[DB server key]',
                            remote_bind_address=('[db ip]', 3306),
                            ) as tunnel:
    # connect MySQL like local                           
        with pymysql.connect(
            host='127.0.0.1', #ssh 터널링을 통해 172.17.44.2의 입장이 되었으므로 localhost로 접속해줌
            user='[db user]',
            passwd='[db password]',
            db='[db name]',
            charset='utf8',
            port=tunnel.local_bind_port,
            cursorclass=pymysql.cursors.DictCursor) as conn:
            with conn.cursor() as cur:
                sql_01 = """
                select e.eventid, g.name , h.name, FROM_UNIXTIME(e.clock,'%Y-%m-%d %H:%i') as event_time, e.name, e.severity 
                from events e
                JOIN triggers t ON e.objectid = t.triggerid
                JOIN functions f ON f.triggerid = t.triggerid
                JOIN items i ON f.itemid = i.itemid
                JOIN hosts h ON h.hostid = i.hostid
                JOIN hosts_groups hg ON hg.hostid = h.hostid
                JOIN hstgrp g on hg.groupid = g.groupid
                where e.clock >= unix_timestamp('"""+ oneweekToStr +"""')
                and e.clock <= unix_timestamp('"""+ nowToStr + """')
                and e.severity >=4
                and e.name not like "%메모리%"
                and e.name not like "%CPU%"
                and e.name not like "%weblogic%"
                order by e.clock desc; 
                """

                
                cur.execute(sql_01)
                error_result = cur.fetchall()

                # for result in error_result:
                    # print(result)
                
                return error_result


def check_run():
    td = today()

    if is_busday(td):
        print(td + " is a business day.")
        host_list = list()
        disk_result_all_now = disk_dayreport(nowToStr, nowToStrPlusOne)
        disk_result_all_yesterday = disk_dayreport(yesterdayToStr, yesterdayToStrPlusOne)
        # print(type(disk_result_all_now))
        # print(type(disk_result_all_now[1]))
        # print(queryTime_yesterday)
        # print(queryTime_yesterday_PlusOne)
        # print(disk_result_all_yesterday)

        # 새로운 호스트일 경우 * 표시 붙임
        for j in disk_result_all_yesterday:
            host_list.append(j['host'])
        for i in disk_result_all_now:
            if i['host'] not in host_list:
                i['host'] = str("* " + i['host'])

        disk_result_all_len_now = len(disk_result_all_now)
        error_result = error_dayreport()
        error_result_len_now = len(error_result)

        send_template_email(template='day_report.html', to="[mail receiver]", subj=day+" 디스크 사용량 및 장애 알람 보고", 
        day=day, disk_result_all_now= disk_result_all_now, disk_result_all_yesterday = disk_result_all_yesterday, error_result = error_result, 
            error_result_len=error_result_len_now, oneweekToStr=oneweekToStr, disk_result_all_len=disk_result_all_len_now)
    else:
        sys.exit(td + " is not a business day.")

check_run()


