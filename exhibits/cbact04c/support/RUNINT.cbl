      ******************************************************************
      * RUNINT - Revenant driver for CBACT04C.
      * Not part of CardDemo. Stands in for the job control statement
      *   EXEC PGM=CBACT04C,PARM='yyyymmddnn'
      * by passing the run date in the mainframe PARM layout:
      * a halfword length followed by the text.
      * Usage: runint <10-character run date>
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. RUNINT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-ARG                  PIC X(80) VALUE SPACES.
       01  WS-PARMS.
           05  WS-PARM-LENGTH      PIC S9(04) COMP VALUE 10.
           05  WS-PARM-DATE        PIC X(10).
       PROCEDURE DIVISION.
           ACCEPT WS-ARG FROM COMMAND-LINE
           IF WS-ARG(1:10) = SPACES OR WS-ARG(11:70) NOT = SPACES
               DISPLAY 'RUNINT: expected one 10-character run date'
               MOVE 16 TO RETURN-CODE
               STOP RUN
           END-IF
           MOVE WS-ARG(1:10) TO WS-PARM-DATE
           CALL 'CBACT04C' USING WS-PARMS
           STOP RUN.
