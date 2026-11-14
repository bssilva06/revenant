      ******************************************************************
      * LOADACCT - Revenant utility, not part of CardDemo.
      * Copies fixed-length 300-byte records from LOADIN into the
      * indexed account file ACCTFILE.
      * Key layout must match FD ACCOUNT-FILE in CBACT04C.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LOADACCT.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO LOADIN
                  ORGANIZATION IS SEQUENTIAL
                  FILE STATUS  IS IN-STATUS.
           SELECT OUT-FILE ASSIGN TO ACCTFILE
                  ORGANIZATION IS INDEXED
                  ACCESS MODE  IS RANDOM
                  RECORD KEY   IS OUT-KEY
                  FILE STATUS  IS OUT-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD  IN-FILE.
       01  IN-REC                  PIC X(300).
       FD  OUT-FILE.
       01  OUT-REC.
           05  OUT-KEY             PIC 9(11).
           05  FILLER              PIC X(289).
       WORKING-STORAGE SECTION.
       01  IN-STATUS               PIC X(02).
       01  OUT-STATUS              PIC X(02).
       01  WS-COUNT                PIC 9(09) VALUE 0.
       PROCEDURE DIVISION.
           OPEN INPUT IN-FILE
           IF IN-STATUS NOT = '00'
               DISPLAY 'LOADACCT: OPEN LOADIN STATUS ' IN-STATUS
               MOVE 12 TO RETURN-CODE
               STOP RUN
           END-IF
           OPEN OUTPUT OUT-FILE
           IF OUT-STATUS NOT = '00'
               DISPLAY 'LOADACCT: OPEN ACCTFILE STATUS ' OUT-STATUS
               MOVE 12 TO RETURN-CODE
               STOP RUN
           END-IF
           PERFORM UNTIL IN-STATUS NOT = '00'
               READ IN-FILE
               IF IN-STATUS = '00'
                   WRITE OUT-REC FROM IN-REC
                   IF OUT-STATUS NOT = '00'
                       DISPLAY 'LOADACCT: WRITE STATUS ' OUT-STATUS
                               ' AT RECORD ' WS-COUNT
                       MOVE 12 TO RETURN-CODE
                       STOP RUN
                   END-IF
                   ADD 1 TO WS-COUNT
               END-IF
           END-PERFORM
           IF IN-STATUS NOT = '10'
               DISPLAY 'LOADACCT: READ STATUS ' IN-STATUS
               MOVE 12 TO RETURN-CODE
               STOP RUN
           END-IF
           CLOSE IN-FILE OUT-FILE
           DISPLAY 'LOADACCT: LOADED ' WS-COUNT
           STOP RUN.
