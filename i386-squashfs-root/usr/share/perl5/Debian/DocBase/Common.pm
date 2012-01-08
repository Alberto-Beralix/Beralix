# vim:cindent:ts=2:sw=2:et:fdm=marker:cms=\ #\ %s
#
# $Id: Common.pm 216 2011-02-20 22:42:12Z robert $


package Debian::DocBase::Common;

use Exporter();
use strict;
use warnings;

use vars    qw(@ISA @EXPORT);
@ISA    = qw(Exporter);
@EXPORT = qw($DATA_DIR $CONTROL_DIR $LOCAL_CONTROL_DIR $VAR_CTRL_DIR $OMF_DIR
             $DOCBASE_SECTIONS_MAP $DOCBASE_VALID_SECTIONS_LIST $CTIME_FIELDNO
             $DB_FILES $DB_STATUS
             @SUPPORTED_FORMATS @NEED_INDEX_FORMATS
             $FLD_DOCUMENT $FLD_VERSION $FLD_SECTION $FLD_TITLE $FLD_AUTHOR $FLD_ABSTRACT 
             $FLD_FORMAT $FLD_INDEX $FLD_FILES 
             %FIELDS_DEF
                $FLDDEF_TYPE
                  $FLDTYPE_MAIN $FLDTYPE_FORMAT
                $FLDDEF_REQUIRED
                $FLDDEF_MULTILINE
             $opt_verbose $opt_debug $exitval $opt_rootdir $opt_update_menus $on_fatal_handler
             $ERR_NONE $ERR_USAGE $ERR_PARSING $ERR_FSACCESS $ERR_PROCESSING $ERR_INTERNAL $ERR_DATABASE
             GetFldKeys
            );

our $DATA_DIR                     = "/var/lib/doc-base/info";
our $DB_FILES                     = "$DATA_DIR/files.yml";
our $DB_STATUS                    = "$DATA_DIR/status.yml";
our $CONTROL_DIR                  = "/usr/share/doc-base";
our $DOCBASE_SECTIONS_MAP         = "$CONTROL_DIR/data/doc-base.map";
our $DOCBASE_VALID_SECTIONS_LIST  = "$CONTROL_DIR/data/section.list";
our $LOCAL_CONTROL_DIR            = "/etc/doc-base/documents";
our $VAR_CTRL_DIR                 = "/var/lib/doc-base/documents";
our $CTIME_FIELDNO                = 10;
our $OMF_DIR                      = "/var/lib/doc-base/omf";

our $ERR_NONE                     = 0;
our $ERR_USAGE                    = 1;
our $ERR_PARSING                  = 2;
our $ERR_PROCESSING               = 3;
our $ERR_FSACCESS                 = 4;  # file system access
our $ERR_INTERNAL                 = 5;
our $ERR_DATABASE                 = 10;  # manipulating *.yml data base files, note the value is used in postinst
# ---configuration-part---

# All formats handled by the doc-base
our @SUPPORTED_FORMATS =  (
                            'html',
                            'text',
                            'pdf',
                            'postscript',
                            'info',
                            'dvi',
                            'debiandoc-sgml'
                      );

# Formats which need the Index: field
our @NEED_INDEX_FORMATS = (
                            'html',
                            'info'
                         );


our $FLD_DOCUMENT   = 'document';
our $FLD_VERSION    = 'version';
our $FLD_SECTION    = 'section';
our $FLD_TITLE      = 'title';
our $FLD_AUTHOR     = 'author';
our $FLD_ABSTRACT   = 'abstract';
our $FLD_FORMAT     = 'format';
our $FLD_INDEX      = 'index';
our $FLD_FILES      = 'files';

# doc-base control file fields definitions
our $FLDDEF_TYPE      = 'type';
  our $FLDTYPE_MAIN   = 1;
  our $FLDTYPE_FORMAT = 2;
our $FLDDEF_REQUIRED  = 'required';
our $FLDDEF_MULTILINE = 'multiline';
our $FLDDEF_POSITION  = 'position';

# Fields in doc-base file:
our %FIELDS_DEF  = (
 # Main fields:
  $FLD_DOCUMENT => {
                  $FLDDEF_POSITION  => 0,
                  $FLDDEF_TYPE      => $FLDTYPE_MAIN,
                  $FLDDEF_REQUIRED  => 1,
                  $FLDDEF_MULTILINE => 0
                },
  $FLD_VERSION  => {
                  $FLDDEF_POSITION  => 1,
                  $FLDDEF_TYPE      => $FLDTYPE_MAIN,
                  $FLDDEF_REQUIRED  => 0,
                  $FLDDEF_MULTILINE => 0
                },
  $FLD_SECTION  => {
                  $FLDDEF_POSITION  => 2,
                  $FLDDEF_TYPE      => $FLDTYPE_MAIN,
                  $FLDDEF_REQUIRED  => 0,
                  $FLDDEF_MULTILINE => 0
                },
  $FLD_TITLE    => {
                  $FLDDEF_POSITION  => 3,
                  $FLDDEF_TYPE      => $FLDTYPE_MAIN,
                  $FLDDEF_REQUIRED  => 1,
                  $FLDDEF_MULTILINE => 1
                },
  $FLD_AUTHOR   => {
                  $FLDDEF_POSITION  => 4,
                  $FLDDEF_TYPE      => $FLDTYPE_MAIN,
                  $FLDDEF_REQUIRED  => 0,
                  $FLDDEF_MULTILINE => 1
                },
  $FLD_ABSTRACT => {
                  $FLDDEF_POSITION  => 5,
                  $FLDDEF_TYPE      => $FLDTYPE_MAIN,
                  $FLDDEF_REQUIRED  => 0,
                  $FLDDEF_MULTILINE => 1
                },
 # Format fields:  
  $FLD_FORMAT   => {
                  $FLDDEF_POSITION  => 6,
                  $FLDDEF_TYPE      => $FLDTYPE_FORMAT,
                  $FLDDEF_REQUIRED  => 1,
                  $FLDDEF_MULTILINE => 0
                },
  $FLD_INDEX    => {
                  $FLDDEF_POSITION  => 7,
                  $FLDDEF_TYPE      => $FLDTYPE_FORMAT,
                  $FLDDEF_REQUIRED  => 0,
                  $FLDDEF_MULTILINE => 0
                },
  $FLD_FILES    => {
                  $FLDDEF_POSITION  => 8,
                  $FLDDEF_TYPE      => $FLDTYPE_FORMAT,
                  $FLDDEF_REQUIRED  => 0, # 
                  $FLDDEF_MULTILINE => 1
                }
);

sub GetFldKeys($) {
  my $fldtype = shift;

  my @fldkeys = sort { $FIELDS_DEF{$a}->{$FLDDEF_POSITION} <=> $FIELDS_DEF{$b}->{$FLDDEF_POSITION} }
                  grep  { $FIELDS_DEF{$_}->{$FLDDEF_TYPE} eq $fldtype }                   
                    keys %FIELDS_DEF;
  return @fldkeys;                  

}

# ---end-of-configuration-part---

# ---global-variables---


our $opt_verbose      = 0;
our $opt_debug        = 0;
our $opt_update_menus = 1;
our $opt_rootdir      = "";
our $exitval          = 0;
our $on_fatal_handler = undef;

1;
