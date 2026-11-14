      ******************************************************************
      * LOADTCAT - Revenant utility, not part of CardDemo.
      * Copies fixed-length 50-byte records from LOADIN into the
      * indexed transaction-category-balance file TCATBALF.
      * Key layout must match FD TCATBAL-FILE in CBACT04C.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LOADTCAT.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO LOADIN
                  ORGANIZATION IS SEQUENTIAL
                  FILE STATUS  IS IN-STATUS.
           SELECT OUT-FILE ASSIGN TO TCATBALF
                  ORGANIZATION IS INDEXED
                  ACCESS MODE  IS RANDOM
                  RECORD KEY   IS OUT-KEY
                  FILE STATUS  IS OUT-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD  IN-FILE.
       01  IN-REC                  PIC X(50).
       FD  OUT-FILE.
       01  OUT-REC.
           05  OUT-KEY             PIC X(17).
           05  FILLER              PIC X(33).
       WORKING-STORAGE SECTION.
       01  IN-STATUS               PIC X(02).
       01  OUT-STATUS              PIC X(02).
       01  WS-COUNT                PIC 9(09) VALUE 0.
       PROCEDURE DIVISION.
           OPEN INPUT IN-FILE
           IF IN-STATUS NOT = '00'
               DISPLAY 'LOADTCAT: OPEN LOADIN STATUS ' IN-STATUS
               MOVE 12 TO RETURN-CODE
               STOP RUN
           END-IF
           OPEN OUTPUT OUT-FILE
           IF OUT-STATUS NOT = '00'
               DISPLAY 'LOADTCAT: OPEN TCATBALF STATUS ' OUT-STATUS
               MOVE 12 TO RETURN-CODE
               STOP RUN
           END-IF
           PERFORM UNTIL IN-STATUS NOT = '00'
               READ IN-FILE
               IF IN-STATUS = '00'
                   WRITE OUT-REC FROM IN-REC
                   IF OUT-STATUS NOT = '00'
                       DISPLAY 'LOADTCAT: WRITE STATUS ' OUT-STATUS
                               ' AT RECORD ' WS-COUNT
                       MOVE 12 TO RETURN-CODE
                       STOP RUN
                   END-IF
                   ADD 1 TO WS-COUNT
               END-IF
           END-PERFORM
           IF IN-STATUS NOT = '10'
               DISPLAY 'LOADTCAT: READ STATUS ' IN-STATUS
               MOVE 12 TO RETURN-CODE
               STOP RUN
           END-IF
           CLOSE IN-FILE OUT-FILE
           DISPLAY 'LOADTCAT: LOADED ' WS-COUNT
           STOP RUN.
