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
                xmlns:mal="http://projectmallard.org/1.0/"
                xmlns:if="http://projectmallard.org/experimental/if/"
                xmlns:dyn="http://exslt.org/dynamic"
                xmlns:func="http://exslt.org/functions"
                xmlns:str="http://exslt.org/strings"
                exclude-result-prefixes="mal if dyn func str"
                extension-element-prefixes="func"
                version="1.0">

<!--!!==========================================================================
Mallard Conditionals
Support for run-time conditional processing.
:Revision:version="1.0" date="2011-04-28" status="review"

This stylesheet contains utilities for handling conditional processing
in Mallard documents.
-->


<!--@@==========================================================================
mal.if.env
The list of env strings.
:Revision:version="1.0" date="2011-04-28" status="review"

This parameter takes a space-separated list of strings for the #{if:env}
conditional processing function. The #{if:env} function will return #{true}
if its argument is in this list.
-->
<xsl:param name="mal.if.env" select="''"/>
<xsl:variable name="_mal.if.env" select="concat(' ', $mal.if.env, ' ')"/>


<!--@@==========================================================================
mal.if.supports
The list of supported technologies.
:Revision:version="1.0" date="2011-07-31" status="review"

This parameter takes a space-separated list of strings for the #{if:supports}
conditional processing function. The #{if:supports} function will return #{true}
if its argument is in this list or @{mal.if.supports.custom}.

Do not change this parameter unless you are completely overriding the behavior
of these stylesheets in a way that removes or changes features. To add support
in a customization, use the @{mal.if.supports.custom} parameter.
-->
<xsl:param name="mal.if.supports" select="'1.0'"/>


<!--@@==========================================================================
mal.if.supports.custom
The list of technologies supported by customizations.
:Revision:version="1.0" date="2011-07-31" status="review"

This parameter takes a space-separated list of strings for the #{if:supports}
conditional processing function. The #{if:supports} function will return #{true}
if its argument is in this list or @{mal.if.supports}.
-->
<xsl:param name="mal.if.supports.custom" select="'1.0'"/>


<xsl:variable name="_mal.if.supports"
              select="concat(' ', $mal.if.supports, ' ', $mal.if.supports.custom, ' ')"/>


<!--**==========================================================================
mal.if.test
Test if a condition is true.
:Revision:version="1.0" date="2011-04-28" status="review"
$node: The element to check the condition for.
$test: The XPath expression to check.

This template tests whether the ${test} is true, evaluating it with
the Mallard conditional functions. The ${test} parameter is expected
to be a valid XPath expression. If not provided, it defaults to the
#{if:test} attribute of ${node}, or the non-namespaced #{test}
attribute if ${node} is an #{if:if} or #{if:when} element.

If ${test} evaluates to #{true}, this template outputs the literal
string #{'true'}. Otherwise, it outputs nothing.
-->
<xsl:template name="mal.if.test">
  <xsl:param name="node" select="."/>
  <xsl:param name="test" select="$node/self::if:if/@test |
                                 $node/self::if:when/@test |
                                 $node[not(self::if:when)]/@if:test "/>
  <xsl:choose>
    <xsl:when test="string($test) = ''">
      <xsl:text>true</xsl:text>
    </xsl:when>
    <xsl:when test="dyn:evaluate($test)">
      <xsl:text>true</xsl:text>
    </xsl:when>
  </xsl:choose>
</xsl:template>


<!--**==========================================================================
mal.if.choose
Gets the position of the first matching condition in #{if:choose}
:Revision:version="1.0" date="2011-04-28" status="review"
$node: The #{if:choose} element to check.

The #{if:choose} element takes a list of #{if:when} elements, optionally followed
by an #{if:else} element. Given an #{if:choose} element, this template outputs
the position of the first #{if:when} whose #{test} attribute evaluates to #{true}.
If no #{if:when} elements are true, the output is empty.
-->
<xsl:template name="mal.if.choose">
  <xsl:param name="node" select="."/>
  <xsl:if test="if:when[1]">
    <xsl:call-template name="_mal.if.choose.try">
      <xsl:with-param name="node" select="if:when[1]"/>
      <xsl:with-param name="pos" select="1"/>
    </xsl:call-template>
  </xsl:if>
</xsl:template>

<xsl:template name="_mal.if.choose.try">
  <xsl:param name="node"/>
  <xsl:param name="pos"/>
  <xsl:variable name="if">
    <xsl:call-template name="mal.if.test">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:variable>
  <xsl:choose>
    <xsl:when test="$if = 'true'">
      <xsl:value-of select="$pos"/>
    </xsl:when>
    <xsl:when test="$node/following-sibling::if:when[1]">
      <xsl:call-template name="_mal.if.choose.try">
        <xsl:with-param name="node" select="$node/following-sibling::if:when[1]"/>
        <xsl:with-param name="pos" select="$pos + 1"/>
      </xsl:call-template>
    </xsl:when>
  </xsl:choose>
</xsl:template>


<!-- ======================================================================= -->

<func:function name="if:env">
  <xsl:param name="env"/>
  <xsl:choose>
    <xsl:when test="contains($_mal.if.env, $env)">
      <func:result select="true()"/>
    </xsl:when>
    <xsl:otherwise>
      <func:result select="false()"/>
    </xsl:otherwise>
  </xsl:choose>
</func:function>

<func:function name="if:supports">
  <xsl:param name="tech"/>
  <xsl:choose>
    <xsl:when test="contains($_mal.if.supports, $tech)">
      <func:result select="true()"/>
    </xsl:when>
    <xsl:otherwise>
      <func:result select="false()"/>
    </xsl:otherwise>
  </xsl:choose>
</func:function>

</xsl:stylesheet>
