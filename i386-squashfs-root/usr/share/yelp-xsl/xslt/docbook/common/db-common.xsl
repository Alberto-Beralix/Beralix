<?xml version='1.0' encoding='UTF-8'?><!-- -*- indent-tabs-mode: nil -*- -->
<!--
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU Lesser General Public License as published by the Free
Software Foundation; either version 2 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
details.

You should have received a copy of the GNU Lesser General Public License
along with this program; see the file COPYING.LGPL.  If not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
02111-1307, USA.
-->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:db="http://docbook.org/ns/docbook"
                xmlns:str="http://exslt.org/strings"
                exclude-result-prefixes="db str"
                version="1.0">

<!--!!==========================================================================
DocBook Common
:Requires: gettext

This stylesheet module provides utility templates for DocBook that are
independant of the target format.
-->

<xsl:key name="idkey" match="*" use="@id | @xml:id"/>


<!--**==========================================================================
db.copyright
Outputs copyright information
$node: The #{copyright} element to format

This template outputs copyright information from a #{copyright} elements.
It assembles the #{year} and #{holder} elements into a simple copyright
notice, beginning with the copyright symbol "©".
-->
<xsl:template name="db.copyright">
  <xsl:param name="node" select="."/>
  <xsl:text>©&#x00A0;</xsl:text>
  <xsl:for-each select="$node/year | $node/db:year">
    <xsl:if test="position() != 1">
      <xsl:call-template name="l10n.gettext">
        <xsl:with-param name="msgid" select="', '"/>
      </xsl:call-template>
    </xsl:if>
    <xsl:apply-templates select="."/>
  </xsl:for-each>
  <xsl:if test="$node/holder | $node/db:holder">
    <xsl:text>&#x00A0;&#x00A0;</xsl:text>
    <xsl:for-each select="$node/holder | $node/db:holder">
      <xsl:if test="position() != 1">
        <xsl:call-template name="l10n.gettext">
          <xsl:with-param name="msgid" select="', '"/>
        </xsl:call-template>
      </xsl:if>
      <xsl:apply-templates select="."/>
    </xsl:for-each>
  </xsl:if>
</xsl:template>


<!--**==========================================================================
db.linenumbering.start
Determines the starting line number for a verbatim element
$node: The verbatim element to determine the starting line number for

This template determines the starting line number for a verbatim element using
the #{continuation} attribute.  The template finds the first preceding element
of the same name, counts its lines, and handles any #{startinglinenumber} or
#{continuation} element it finds on that element.
-->
<xsl:template name="db.linenumbering.start">
  <xsl:param name="node" select="."/>
  <xsl:choose>
    <xsl:when test="$node/@startinglinenumber">
      <xsl:value-of select="$node/@startinglinenumber"/>
    </xsl:when>
    <xsl:when test="$node/@continuation">
      <xsl:variable name="prev" select="$node/preceding::*[name(.) = name($node)][1]"/>
      <xsl:choose>
        <xsl:when test="count($prev) = 0">1</xsl:when>
        <xsl:otherwise>
          <xsl:variable name="prevcount">
            <xsl:value-of select="count(str:split(string($prev), '&#x000A;'))"/>
          </xsl:variable>
          <xsl:variable name="prevstart">
            <xsl:call-template name="db.linenumbering.start">
              <xsl:with-param name="node" select="$prev"/>
            </xsl:call-template>
          </xsl:variable>
          <xsl:value-of select="$prevstart + $prevcount"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:when>
    <xsl:otherwise>1</xsl:otherwise>
  </xsl:choose>
</xsl:template>


<!--**==========================================================================
db.orderedlist.start
Determines the number to use for the first #{listitem} in an #{orderedlist}
$node: The #{orderedlist} element to use

This template determines the starting number for an #{orderedlist} element using
the #{continuation} attribute.  Thi template finds the first preceding #{orderedlist}
element and counts its list items.  If that element also uses the #{continuation},
this template calls itself recursively to add that element's starting line number
to its list item count.
-->
<xsl:template name="db.orderedlist.start">
  <xsl:param name="node" select="."/>
  <xsl:choose>
    <xsl:when test="$node/@continutation != 'continues'">1</xsl:when>
    <xsl:otherwise>
      <xsl:variable name="prevlist"
                    select="$node/preceding::orderedlist[1]"/>
      <xsl:choose>
        <xsl:when test="count($prevlist) = 0">1</xsl:when>
        <xsl:otherwise>
          <xsl:variable name="prevlength" select="count($prevlist/listitem)"/>
          <xsl:variable name="prevstart">
            <xsl:call-template name="db.orderedlist.start">
              <xsl:with-param name="node" select="$prevlist"/>
            </xsl:call-template>
          </xsl:variable>
          <xsl:value-of select="$prevstart + $prevlength"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>


<!--**==========================================================================
db.personname
Outputs the name of a person
$node: The element containing tags such as #{firstname} and #{surname}
$lang: The language rules to use to construct the name

This template outputs the name of a person as modelled by the #{personname}
element.  The #{personname} element allows authors to mark up components of
a person's name, such as the person's first name and surname.  This template
assembles those into a string.
-->
<xsl:template name="db.personname">
  <xsl:param name="node" select="."/>
  <!-- FIXME: call i18n.locale -->
  <xsl:param name="lang" select="ancestor-or-self::*[@lang][1]/@lang |
                                 ancestor-or-self::*[@xml:lang][1]/@xml:lang"/>

  <xsl:if test="$node/db:personname">
    <xsl:call-template name="db.personname">
      <xsl:with-param name="node" select="$node/db:personname"/>
      <xsl:with-param name="lang" select="$lang"/>
    </xsl:call-template>
  </xsl:if>
  <!-- FIXME: Use xsl:choose for different language rules -->
  <xsl:if test="$node/honorific or $node/db:honorific">
    <xsl:apply-templates select="$node/honorific[1] | $node/db:honorific[1]"/>
  </xsl:if>
  <xsl:choose>
    <xsl:when test="$node/@role = 'family-given'">
      <xsl:if test="$node/surname or $node/db:surname">
        <xsl:if test="$node/honorific or $node/db:honorific">
          <xsl:text> </xsl:text>
        </xsl:if>
        <xsl:apply-templates select="$node/surname[1] | $node/db:surname[1]"/>
      </xsl:if>
      <xsl:if test="$node/othername or $node/db:othername">
        <xsl:if test="$node/honorific or $node/surname or
                      $node/db:honorific or $node/db:surname">
          <xsl:text> </xsl:text>
        </xsl:if>
        <xsl:apply-templates select="$node/othername[1] |
                                     $node/db:othername[1]"/>
      </xsl:if>
      <xsl:if test="$node/firstname or $node/db:firstname">
        <xsl:if test="$node/honorific or $node/surname or $node/othername or
                      $node/db:honorific or $node/db:surname or
                      $node/db:othername">
          <xsl:text> </xsl:text>
        </xsl:if>
        <xsl:apply-templates select="$node/firstname[1] |
                                     $node/db:firstname[1]"/>
      </xsl:if>
    </xsl:when>
    <xsl:otherwise>
      <xsl:if test="$node/firstname or $node/db:firstname">
        <xsl:if test="$node/honorific or $node/db:honorific">
          <xsl:text> </xsl:text>
        </xsl:if>
        <xsl:apply-templates select="$node/firstname[1] |
                                     $node/db:firstname[1]"/>
      </xsl:if>
      <xsl:if test="$node/othername or $node/db:othername">
        <xsl:if test="$node/honorific or $node/firstname or
                      $node/db:honorific or $node/db:firstname">
          <xsl:text> </xsl:text>
        </xsl:if>
        <xsl:apply-templates select="$node/othername[1] |
                                     $node/db:othername[1]"/>
      </xsl:if>
      <xsl:if test="$node/surname or $node/db:surname">
        <xsl:if test="$node/honorific or $node/firstname or $node/othername or
                      $node/db:honorific or $node/db:firstname or
                      $node/db:othername">
          <xsl:text> </xsl:text>
        </xsl:if>
        <xsl:apply-templates select="$node/surname[1] | $node/db:surname[1]"/>
      </xsl:if>
    </xsl:otherwise>
  </xsl:choose>
  <xsl:if test="$node/lineage or $node/db:lineage">
    <xsl:text>, </xsl:text>
    <xsl:apply-templates select="$node/lineage[1] | $node/db:lineage[1]"/>
  </xsl:if>
</xsl:template>


<!--**==========================================================================
db.personname.list
Outputs a list of people's names
$nodes: The elements containing tags such as #{firstname} and #{surname}
$lang: The language rules to use to construct the list of names

This template outputs a list of names of people as modelled by the #{personname}
element.  The #{personname} element allows authors to mark up components of a
person's name, such as the person's first name and surname.  This template makes
a list formatted according to the locale set in ${lang} and calls the template
*{db.personname} for each element in ${nodes}.
-->
<xsl:template name="db.personname.list">
  <xsl:param name="nodes"/>
  <!-- FIXME: call i18n.locale -->
  <xsl:param name="lang" select="ancestor-or-self::*[@lang][1]/@lang |
                                 ancestor-or-self::*[@xml:lang][1]/@xml:lang"/>
  <xsl:for-each select="$nodes">
    <xsl:choose>
      <xsl:when test="position() = 1"/>
      <xsl:when test="last() = 2">
        <xsl:call-template name="l10n.gettext">
          <xsl:with-param name="msgid" select="' and '"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="position() = last()">
        <xsl:call-template name="l10n.gettext">
          <xsl:with-param name="msgid" select="', and '"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:call-template name="l10n.gettext">
          <xsl:with-param name="msgid" select="', '"/>
        </xsl:call-template>
      </xsl:otherwise>
    </xsl:choose>
    <xsl:call-template name="db.personname">
      <xsl:with-param name="node" select="."/>
      <xsl:with-param name="lang" select="$lang"/>
    </xsl:call-template>
  </xsl:for-each>
</xsl:template>

</xsl:stylesheet>
